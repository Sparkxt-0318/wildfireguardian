# CRITIC_LATEST — critic #13, 2026-09-04

Window `3d77e01..baf6962` on `auto/dev` (13 commits). Written by the `wfg-autoloop-critic`
routine. The next dev lap clears every `fix-before-next-row` item here before claiming a row.

## fix-before-next-row

**None this lap.** Under CHARTER §14b an item qualifies only on a judge-facing surface or a
red gate. The red gate is closed and I verified the closure rather than trusting the report
that claimed it. Nothing judge-facing is broken: the two documents critic #12 named are both
repaired, and I re-derived their claims from the artifacts. **So the next dev lap owes this
routine nothing and can spend itself entirely on a product row.** That is the intended reading,
not a formality.

## Verified independently this lap

`gates.py --mode full` exits **0** at `baf6962` in a fresh cloud sandbox: `1377 passed,
62 skipped` in 178 s, **COLD** (first full run in this sandbox, so the six SRTM-gated tests
skip; WFG-039). Against critic #12's cold `1376 / 62` at `c65dc56` that is **+1 passed, skips
unchanged**, like for like, seventh comparable window. `verify`, `snapshot-verify`, `env-check`
PASS; `baseline-verify` WARN, expected off-laptop, `hard: false`, thirteenth window and still
not a finding. Green at HEAD for a **tenth** consecutive critic lap.

**GitHub's own runs (CHARTER §4b), read through the MCP because the sandbox proxy answers 403
to unauthenticated `api.github.com` calls.** Six red `auto-gates` runs sit in this window's
history: runs 86–91, heads `201c554`, `89730db`, `6f33eca`, `ced9430`, `3d77e01`, `e4a7304`,
every one of them pushed by a lap that read ALL GREEN in its own sandbox. **Already diagnosed
and already fixed**, and the diagnosis is exact: `tests/test_finals_screen.py::test_the_stamp_gate_is_graded_against_the_ways_a_stamp_goes_wrong`
builds a probe commit with `git commit-tree`, which is the only git **write** in the suite, and
it inherited a committer identity that `actions/checkout` does not configure. Fixed at
`21b8740`; runs 92, 93 and 95 are `success`, run 94 was cancelled by a superseding push, and
run 95 is this head. So this is **not** finding #1 and **not** the fix-before-next-row item.
The residue that is worth naming and that nobody has: the first red was **16:03Z** and the fix
**18:39Z**, **2 h 36 min against §4b's 「catch it within the hour」**, and the hourly ci-red
routine's own run on it produced a report and no fix because a concurrent lap had landed the
same repair fifteen minutes earlier.

**Report certification.** Every push in the window carried a report. 19 of the 20 dev reports
in the last 24 h record `Reviewed by:`; `docs/auto/reports/2026-09-04T0401Z-dev.md` does not,
although its commit list records two reviewer blocks, so the review happened and only the line
is missing.

## Critic #12's three capping defects: two closed, verified from the files

- **WFG-057 closed.** `docs/auto/JUDGE_QA.md` says 41 questions and 15 / 19 / 7; counting the
  file gives **41 questions, 15 / 19 / 7**. The four drill rounds now name all 41 by number
  where they had been naming 33, and **Q10d, which is T0, was in no drill round at all** until
  this window. The regex reads the lettered suffix and the parenthesised provenance, so the
  next question added makes the header and the drill table wrong together.
- **WFG-081 closed.** Q35 no longer scripts the student to open with 「아니오」 about a defect
  fixed nine hours earlier. Verified: `web/finals.html` carries `"git":"d5e2562"`,
  `git cat-file -t` resolves it, `git merge-base --is-ancestor d5e2562 HEAD` succeeds in this
  fresh clone, and `tests/test_finals_screen.py` holds **32** tests, two of which read that
  line — all three supporting claims in the rewritten answer hold.
- **WFG-079 open.** `docs/juso_yeongdeok.md:61` still writes the 「약 45 km」 its own `:15`
  forbids in bold and names 봉화군 which its own `:29` refuses to name without 행정표준코드;
  `:58` still records two zero-row layers as facts about the county. Minutes of work.

## Judge drill

All **77 distinct file paths** the Q&A bank cites resolve (five are directory-relative
shorthands). Drilled the hardest T0, **Q1**, against the artifacts rather than the prose:
pooled recall **0.138**, mean-of-folds **0.0867**, average precision **0.169**, prevalence
**0.0197**, advance threshold 0.3, router cut 0.5 — every figure re-derives from
`data/processed/operating_point/per_fire_recall.json` and `docs/NUMBERS.json` exactly as the
answer states. **No question went unanswerable from a file this lap**, so no 「근거 없음」 entry
was added. The one already open, Q34 (spread rate, WFG-065), is open for a fourth window.

## Root objection

**The loop now spends about half of everything it writes on describing and steering itself.**
Measured over the 24 h window `1113388..baf6962`: **108 commits, 25,122 authored text lines**
(images and the generated board excluded). `docs/auto/reports/` took **9,000 lines in 49 new
report files** (35.8 %, mean 184 lines each). The steering documents took **3,386** (13.5 %).
Together **49.3 %**. Everything a judge will ever see — `docs/auto/JUDGE_QA.md`, `web/`,
`README.md`, `docs/auto/finals/` — took **663 lines, 2.6 %**. **Nineteen lines about the loop
for every one line at the booth**, on the first day of a twelve-day sprint, with three of
eleven readiness lines ticked and none ticked for four critic laps.

The visible cost is already in the steering documents themselves: `CHARTER.md` now carries
**section 3c twice**, with two different texts written by two laps for one decision (`:436`
and `:457`), and its tail runs 13, 6b, 14, 14b, 3c, 4b, 3c. The document every lap is told to
read first is the only document in the tree with no gate, and it has started repeating itself.

**Cheapest test.** Cap the report: the next three dev laps write at most 120 lines of summary
(the gate table, the findings, the reviewer verdict, `## In plain terms`; the long evidence
goes in the commit message, where it already is) and spend the reclaimed effort on a booth
row. If `KCF_READINESS.md` ticks a line inside those three laps, the reports were the cost.
If it does not, the reports were never the bottleneck and this objection is wrong. Filed as
**WFG-084**, P1 under §14b.

## What this lap changed in the backlog

- **WFG-077 was two different rows.** `1c5ae23` filed the NH-023 staging gate as WFG-077 and
  critic #12 at `3d77e01` filed the report-certification row under the same ID fifteen minutes
  earlier; a dev lap told to take WFG-077 could not know which. The critic-authored P0 row is
  renumbered **WFG-082**, keeping the id that `CHARTER.md:465`, `MEMO.md:753` and two reports
  quote. No duplicate IDs remain in the table (checked mechanically).
- **WFG-083** (P1) — fold the duplicated CHARTER §3c, put the lettered sections next to their
  parents, and gate against two headings sharing a number.
- **WFG-084** (P1) — cap the report; the structural half of the root objection.
- **No row was moved.** I moved WFG-003 above WFG-062 under §14b and then put it back on
  finding **NH-024** already open, with 「hand the booth rows their place back」 spelled out as
  its option C. Critic #12's re-scope test has resolved and the answer is due, but it is the
  author's; a critic that reorders under its own loop's open escalation makes the escalation
  theatre. NH-024 carries this lap's measurement so the author can decide on it.
