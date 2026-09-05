# KCF readiness — the final product's definition of done

The critic lap ticks every line daily with a commit or file as evidence, in the
`evidence` column; an unticked line is a finding, and the product is not ready
until every line is ticked. The dev laps work WFG-036 until it is. Dates: freeze
2026-10-16, finals 2026-10-24 (김대중컨벤션센터, Gwangju, offline booth).

**Tick count, critic #21, 2026-09-05T2000Z: 4 of 11 (R2, R4, R5, R6). No line moved, and no line has moved
for SIX consecutive critic laps (#16 to #21) — and this window is the one where that sentence means
something different.** Checked on disk at `492364c`, not read from the laps that claimed it:

- **No line moved because the window is one line long.** `git diff 3efd0db..HEAD` is a single changed
  line: the status cell of one backlog row. The 18:17Z dev lap pushed `492364c`
  (`claim WFG-114 (20260905T1820Z)`) at 18:20Z and nothing since; at 20:10Z that is 1 h 50 m. No
  WFG-114 artifact exists under `data/processed/` and `git log --all --grep=WFG-114` finds only the
  claim and critic #20's report. **So the 「zero for two consecutive critic laps」 rule fires for a
  sixth lap, and for the first time the cause is not the queue and not the direction page.** Critic
  #20's falsifiable test is half-resolved and it resolved **for** the page: the lap took WFG-114, the
  row the page named and the author promoted. Then it produced nothing. Filed as **NH-030**; the
  release rule for the next lap is in `docs/auto/CRITIC_LATEST.md` and no claim was released here.
- **R3's sandbox half is green and its booth half is exactly where the author left it.** `gates.py
  --mode full` exits 0 in this fresh cloud sandbox at `492364c` (`1515 passed, 62 skipped` in 253.2 s,
  **COLD**, against critic #20's cold `1515 / 62` at `ce262fe`: **unchanged like for like**, which is
  what a one-line window should produce). `verify`, `snapshot-verify` and `env-check` PASS.
  `--assert-head` exits 0. **NH-029's measurement re-run rather than quoted:** `make baseline-verify`
  here reports `BASELINE MOVED — 2 difference(s) against 944243054a59`, and both are the git-ignored
  `data/raw/firms_data/` manifests that exist only on the author's machine. Critic #20's reading holds.
  R3 still waits on one `make all-checks` run on the author's own laptop.
- **R3's CI half is clean, read through the GitHub MCP because this routine's own command has stopped
  working.** `auto-gates` runs **131 to 139** on `auto/dev` carry **no `failure`**; 139 at this head is
  `success`; 137 and 131 were `cancelled` by a superseding push. ⚠ The step-2 command in this routine's
  prompt, `curl https://api.github.com/repos/Sparkxt-0318/wildfireguardian/actions/runs`, now returns
  **403** 「GitHub access is not enabled for this session」 from the sandbox proxy. Filed as **WFG-119**.
  All 44 consecutive push pairs in the 24-hour window pass `--assert-reported`, and every dev, paper and
  critic report in it carries `Reviewed by:` (the five without it are `manual`, the author's own laptop).
- **R5 keeps its tick and takes a defect on it, recorded the way WFG-067, WFG-095, WFG-100, WFG-103 and
  WFG-109 were: WFG-117, and it is this lap's one `fix-before-next-row` item.** The judge drill found it:
  `JUDGE_QA.md` Q30 is **T0**, it is the question about why today's numbers should be believed, and its
  drafted answer has the student say 「등록된 값 295개 중 261개」 with the remaining 34 split 16 + 18. I
  counted `docs/NUMBERS.json` myself: **326** entries, **268** reproducible, **58** not. The screen
  behind the student prints **326 · 재현 가능 268** in the same 검증 레지스트리 card. Nothing gates it —
  `tests/test_judge_qa_bank.py` reads no registry count — which is how they drifted 31 apart. A ⚠ 근거
  없음 note is on Q30 as of this lap so the student does not rehearse it. The tick survives because the
  bank's own self-count (41 questions, 15 / 19 / 7) is correct, re-counted here.
- **R1 is unchanged and WFG-115 survives an independent re-test with a confounder removed.** Critic #20
  proved `41498ef` is not reachable from `HEAD`. That test was run in a **depth-50 shallow clone**
  (`git rev-parse --is-shallow-repository` → `true`, `git rev-list --count HEAD` → 50), where
  `merge-base --is-ancestor` cannot answer across the boundary, and no critic lap has ever recorded that
  the sandbox is shallow. I ran `git fetch --deepen=120` (170 commits) and re-ran it: `41498ef` is
  **still** not an ancestor, and it is still on `origin/auto/lap-b1989d5-superseded` and
  `origin/ordering-boundary` only. WFG-115 stands. The shallow clone itself is **WFG-119**, with a
  predicted failure it has not yet caused: the screen's stamp `5f9a3b8` is 7 commits behind `HEAD`, the
  branch moves on the order of 40 commits a day, and once a stamp ages past 50 commits the ancestry gate
  goes RED in every sandbox while staying GREEN in CI, which checks out at `fetch-depth: 0`.
- **R7 and half of R9, sixth day, and this is now the longest-standing unticked line with a P0 row
  behind it.** `docs/auto/finals/` holds `BOOTH_SETUP.md`, `DETECTION_FLOOR_CARD.md` and one screenshot
  folder; `find . -iname '*.pdf'` outside `outputs/` and the venv returns nothing. WFG-007 is P0 and
  `todo` at table position 3, where critic #20 put it. R9's mechanism was re-run here rather than
  quoted: `make finals-bundle` exits 0 with `OK — release/kcf-finals-2026/ rebuilt byte-identically,
  17 files`.
- **Census for the window:** 1 authored insertion, 1 deletion, 1 file. There is no judge-facing share to
  report and no report share; WFG-084's series takes no sixth data point from a window with no work in it.

*(Critic #20's count block, which stood here until 2026-09-05T2000Z, is preserved verbatim below.)*

**Tick count, critic #20, 2026-09-05T1700Z: 4 of 11 (R2, R4, R5, R6). No line moved, and no line has moved
for FIVE consecutive critic laps (#16 to #20).** Checked on disk at `ce262fe`, not read from the laps that
claimed it:

- **R3 moved materially without moving the box, and the author is why.** Critic #19's NH-029 was answered:
  the author ran `make baseline-freeze` on the laptop at `38620f2`. Re-run here rather than quoted,
  `make baseline-verify` now reports **2** differences against `944243054a59`, not six, and **both** are the
  git-ignored `data/raw/firms_data/` manifests that exist only on the author's machine. The four
  in-every-clone differences are gone. ⚠ **And the re-freeze preserved every protection**, which is the thing
  CHARTER §3.2 exists for and which a sandbox re-freeze would have destroyed: diffing `38620f2^` against
  `38620f2`, both `untracked_contracts` hashes and all four `protected` artifact hashes are byte-identical,
  and `tracked_processed` went 127 to 130 (the three `pace_*.json` files). **Still ☐** on one thing only: one
  `make all-checks` run on the author's own machine, which is NH-029's remaining half.
- **R3's CI half is clean.** `auto-gates` runs 117 to 136 on `auto/dev` carry **no `failure`**; 136 at this
  head is `success`; 131 and 125 were `cancelled` by a superseding push (WFG-102). `gates.py --mode full`
  exits 0 in this fresh cloud sandbox at `ce262fe` (`1515 passed, 62 skipped` in 202.0 s, **COLD**, against
  critic #19's cold `1506 / 62`: **+9 like for like**). `verify`, `snapshot-verify` and `env-check` PASS.
  Every consecutive pair of commits in the window passes `--assert-reported`, and every dev, paper and critic
  report in the last 24 h carries `Reviewed by:` (the four without it are `manual`, the author's own laptop).
- **R7 and half of R9 are still held by one object that no lap has ever claimed: the printables.**
  `docs/auto/finals/` holds `BOOTH_SETUP.md`, `DETECTION_FLOOR_CARD.md` and one screenshot folder, and no PDF
  (`find . -iname '*.pdf'` outside `outputs/` and the venv returns nothing new). Critic #19 wrote the
  falsifiable test — 「if WFG-109 closes and the printables still do not exist, WFG-007's **priority** is the
  defect」 — WFG-109 is `done(20260905T1520Z)`, and **this lap raised WFG-007 from P1 to P0** and put it second
  on `docs/auto/DIRECTION.md`. That is the whole of this lap's row-move budget.
- **R1 is now further away than it was, and by a new fact rather than an old one.** Beyond WFG-110's six
  unmapped registry keys, the screen prints a second commit id, `41498ef`, which
  `git merge-base --is-ancestor 41498ef HEAD` **rejects** (WFG-115). R1 asks that every on-screen number map
  to a registry key; a provenance line that maps to a commit not on this branch is the same class of defect
  and is now named on the line.

*(Critic #19's count block, which stood here until 2026-09-05T1700Z, is preserved verbatim below. Nothing is
deleted; the newest count is the one above.)*

**Tick count, critic #19, 2026-09-05T1400Z: 4 of 11 (R2, R4, R5, R6). No line moved this window, and no line
has moved for FOUR consecutive critic laps (#16, #17, #18, #19).** The 「zero for two consecutive critic
laps」 rule fires again, and this lap's reading of it is different from the last three and is written up in
`docs/auto/DIRECTION.md`: **the loop built exactly the artifact the last three critics named, and the lines
still did not move, so the queue is no longer what holds them.** Checked on disk at `92bfc4f`, not read from
the laps that claimed it:

- **R3's booth half now has a written recipe, and R3 is further from tickable than it looked.**
  `docs/auto/finals/BOOTH_SETUP.md` EXISTS (256 lines, Korean, WFG-037, `5aecc5f`) and I read it rather than
  the report. Its citations resolve: `web/finals.html:2154` is `lang === 'ko' ? 'EN' : 'KO'` and
  `web/finals.html:2145` is the `state.view === 'live'` guard on keys 1-4, both exactly as §5.6 and §6 say.
  ⚠ **But the line's own command still does not pass, and now nobody can claim off-laptop for it.** I ran
  `make baseline-verify` myself: `BASELINE MOVED — 6 difference(s) against 89730db89921`, of which only the
  two `data/raw/firms_data/` manifests are sandbox conditions; `registry_entries: 320 -> 326` and three
  tracked `data/processed/demo_script_pace/pace_*.json` artifacts are in **every clone**, the author's
  included. Eighteen critic laps, mine included, wrote 「`baseline-verify` WARN, expected off-laptop,
  `hard: false`」 and read past four differences that are not. That is **NH-029** and it is the best thing
  this window produced.
- **R3's CI half is clean.** `auto-gates` run **130 at `92bfc4f` (this head) is `success`**; runs 130, 129,
  128, 127, 126, 124, 123, 122, 121, 120, 119, 118, 117, 113, 112 and 111 are `success`, and 125, 116 and
  115 were `cancelled` by a superseding push. **No `failure` at all in this window, and no red run stands
  behind a green report.** `gates.py --mode full` exits 0 in this fresh cloud sandbox at `92bfc4f`
  (`1506 passed, 62 skipped` in 197.4 s, **COLD**, against critic #18's `1490 / 56` warm and critic #17's
  cold `1484 / 62` at `26e200d`: **+22 passed like for like**). `verify`, `snapshot-verify` and `env-check`
  PASS. Fifteen of fifteen pushes in the window pass `--assert-reported`, and every dev, paper and manual
  report in it carries a `Reviewed by:` line.
- **R7 and R9 are held by one object and it is the same one as yesterday and the day before: the
  printables.** `docs/auto/finals/` holds `BOOTH_SETUP.md`, `DETECTION_FLOOR_CARD.md` and one screenshot
  folder, and **no printable, PDF or otherwise** (WFG-007, P1, never claimed). I re-ran `make finals-bundle`:
  exit 0, `OK — release/kcf-finals-2026/ rebuilt byte-identically, **17** files` (16 last window; the new
  file is `check_bundle_copy.py`, which travels in the bundle). I also ran the new checker on the built
  folder: `OK — release/kcf-finals-2026 matches its own MANIFEST.json.` The bundle carries the Korean fonts,
  so §7.2's 「한국어 글꼴은 꾸러미 안에 있습니다」 is true: `IBMPlexSansKR-{Regular,SemiBold}.woff2` and
  `Pretendard-arrow.subset.woff2` are three of the seventeen.
- **R1 is measured for the first time in nineteen laps, and it is six rows wide (WFG-110).** Critic #18 wrote
  「no such table exists」; that is too strong. `docs/auto/DEMO_SCRIPT_5MIN.md` §3 is a mapping table, but it
  runs script → key, and R1 asks screen → key. Using §3's own criterion for 화면 (does
  `scripts/finals.template.html` reference the key), the template references **28** registry keys, §3 names
  **22**, and **6** are in no committed table: `objective_canonical_longest_walk_saving_min`,
  `oof_average_precision`, `rescue_dispatch_count`, `responder_exposure_shortest_path_mean`,
  `responder_exposure_survival_aware_mean`, `slope_canonical_fa_routes_changed_60m`. R1's other half gained
  its first evidence this window (`BOOTH_SETUP.md` §3: headless Chromium, `file://`, network blocked, 0
  external requests on all four screens); **I did not reproduce that browser run** and do not tick on it.
- **R4 keeps its tick and gains one defect on it, recorded the way WFG-067, WFG-095, WFG-100 and WFG-103
  were: WFG-109.** `scripts/finals.template.html:1378` (KO) and `:1381` (EN) still carry the STATIC VIEW
  sentence WFG-103 withdrew, while the built `web/finals.html:1378`/`:1381` carry the correction. I diffed
  both files. Nothing is wrong on the judged screen today; the next `make finals` reverts it, and no gate
  reads the template. **This is critic #19's one `fix-before-next-row` item.** The window's one change to
  `DEMO_SCRIPT_5MIN.md` is §0's language-button line and it is correct.
- **Census for the window, measured** (`e2628f3..92bfc4f`, images, the `.docx` and the generated board
  excluded): **1,141 authored insertions, of which 272 (23.8 %) reached a judge-facing surface** — 256 of
  them `docs/auto/finals/BOOTH_SETUP.md` itself, 14 the bundle's `README_KO.md`, 2 the demo script — and
  **216 (18.9 %) are the report**. The largest remaining block, **481 lines (42.2 %), is two test files**
  (`tests/test_check_bundle_copy.py`, `tests/test_booth_setup.py`) that gate the judge-facing artifact.
  Prior windows: 6.2 %, 1.8 %, 21.8 %, 27.3 % judge-facing. **Fifth data point for WFG-084 and the highest
  judge-facing share this census has recorded**, on the first window since its cap became this routine's rule.

Previous count: **critic #18, 2026-09-05T1100Z: 4 of 11 (R2, R4, R5, R6). No line moved this window, and no line
has moved for THREE consecutive critic laps (#16, #17, #18).** That fires the 「zero for two consecutive critic
laps」 rule, and under this file's own wording it is a finding about the loop's direction and not about the
product. It is written up in `docs/auto/DIRECTION.md`, and the action taken on it is that critic #18 set **no**
`fix-before-next-row` item and moved WFG-037 above WFG-104, so the next dev lap owes the critic nothing and the
first row it meets is `BOOTH_SETUP.md`. Checked on disk at `6afd252`, not read from the laps that claimed it:

- **R1 could not move on its condition, though `web/` did change.** `web/finals.html` gained two lines this
  window (WFG-103, the STATIC VIEW caption in KO and EN) — so the sentence 「nothing touched `web/`」 is **not**
  true of this window and must not be repeated. R1 is unmoved for a different reason: its condition is a
  committed mapping table from every on-screen number to a `docs/NUMBERS.json` key, and no such table exists at
  this head (searched `docs/finals_screen_v2.md` and `docs/auto/DEMO_SCRIPT_5MIN.md`).
- **R3 (booth half), R7 and R9 are held by the same two absent artifacts as yesterday and the day before**,
  both checked on disk at this head: `docs/auto/finals/BOOTH_SETUP.md` does not exist (WFG-037) and
  `docs/auto/finals/` holds one card and one screenshot folder and no printable, PDF or otherwise (WFG-007).
  I re-ran `make finals-bundle` myself rather than reading critic #17's result: exit 0, `OK —
  release/kcf-finals-2026/ rebuilt byte-identically, 16 files`. R9's mechanism works for a third window; R9's
  contents still do not exist. **WFG-037 has never been claimed by any lap** (`git log -S` over this file's
  history finds it only in reorders), which is the whole of the direction finding above.
- **R3's CI half is clean.** `auto-gates` run **124 at `6afd252` (this head) is `success`**; 123, 122, 121,
  120, 119, 118 and 117 are `success`, 116 and 115 were `cancelled` by the next push. **No red run stands
  behind a green report in this window.** The last `failure` is run 110 (`d2418c2`, 03:20Z), already filed as
  NH-026 and WFG-102.
- **R4 keeps its tick and WFG-103 is closed on it, on both surfaces rather than the one the finding named.**
  The script's 3막 and `web/finals.html`'s STATIC VIEW caption both stopped calling the fire-blind arm 「지금 이
  순간만 보는 지도」. I re-derived the re-measure that followed: 161+246+280+346+331+328 = **1,692**;
  28+44+50+61+59+58 = **300**; per-segment 5.75 / 5.59 / 5.60 / 5.67 / 5.61 / 5.66, spread **1.03x**. Every
  cell holds. ⚠ **The new defect on this line is that the two surfaces now disagree**: the screen says only what
  is measured, the script adds 「이 도구가 없을 때의 기준선입니다」, a counterfactual the repository labels and has
  never measured. Recorded on the ticked line the way WFG-067, WFG-095, WFG-100 and WFG-103 were; it is folded
  into **WFG-104**, and it is **not** this lap's `fix-before-next-row` item because this lap sets none.
- **Census for the window, measured** (`6236c81..6afd252`, images, `.docx` and the generated board excluded):
  **1,043 authored insertions, of which 65 (6.2 %) reached a judge-facing surface and 493 (47.3 %) are
  reports** — the highest report share this census has recorded, on the window whose falsifiable test was
  about exactly that. Prior windows: 27.3 %, 21.8 %, 1.8 % judge-facing. Fourth data point for WFG-084, and
  the one that turns its cap from a proposal into this routine's rule.

Previous count: **critic #17, 2026-09-05T0800Z: 4 of 11 (R2, R4, R5, R6). No line moved this window.** R4 was
ticked inside the last 24 h (critic #15, `43710f7`, 0200Z), so the「zero for two consecutive critic laps」
direction finding does **not** fire. Checked on disk at `26e200d`, not read from the laps that claimed it:

- **R1 could not move.** Nothing has touched `web/` since `deeb147` (2026-09-04T15:59Z) and the screen's
  content is unchanged since `dc63a06` (2026-09-04T07:14Z) — the sentence critic #16 corrected this file
  to, used here as written.
- **R3 (booth half), R7 and R9 are held by the same two absent artifacts as yesterday**, both checked on
  disk at this head: `docs/auto/finals/BOOTH_SETUP.md` does not exist (WFG-037) and `docs/auto/finals/`
  still holds one card and one screenshot folder and no printable (WFG-007). I re-ran `make finals-bundle`
  myself rather than reading critic #16's result: exit 0, `OK — release/kcf-finals-2026/ rebuilt
  byte-identically, 16 files`. R9's mechanism works; R9's contents do not exist.
- **R3's CI half is clean.** `auto-gates` run **117 at `26e200d` (this head) is `success`**; 116 and 115
  were `cancelled` by the next push, 114 and 113 `success`. No red run stands behind a green report in this
  window. The last `failure` is run 110 (03:20Z), already filed as NH-026 and WFG-102 and outside it.
- **R4 keeps its tick and WFG-100 is closed on it.** The cell below records the re-budget; I re-derived
  every cell of `docs/demo_script_pace.md`'s table and they hold. **The new defect on this line is
  WFG-103** and it is not about the clock: `docs/auto/DEMO_SCRIPT_5MIN.md:108-109`, inside 3막, tells the
  judge the comparison is against 「지금 이 순간만 보는 지도」 while the arm is fire-blind
  (`src/wildfireguardian/routing/evacuation.py:270`, `docs/real_roads_real_hazard.md:50`). Recorded on the
  ticked line the way WFG-067, WFG-095 and WFG-100 were; one sentence, and it is this lap's one
  `fix-before-next-row` item. **WFG-105** carries the second half of the clock question — 5.61 syl/s is
  charged against all 300 s while §2 guarantees five interruptions inside them, and the published Korean
  *articulation* rate (pauses excluded) is 5.2–6.4 syl/s, so a *speaking* rate of 5.61 sits inside a band
  that excludes exactly what it must contain. NH-014 carries the amendment.
- **Census for the window, measured:** 1,542 authored insertions, of which **28 (1.8 %)** reached a
  judge-facing surface, against 21.8 % and 27.3 % in the two windows before. That is not a slippage note:
  the 28 lines are a correction to `DEMO_SCRIPT_5MIN.md` and the other 1,504 are the measurement apparatus
  that justified it, which is reusable and goes red on the next edit of the script. Whether that ratio is
  the right price is exactly WFG-084's open question, and this is the third data point for it.

Previous count: **critic #16, 2026-09-05T0530Z: 4 of 11 (R2, R4, R5, R6). No line moved this window, and
that is the right answer rather than a slippage note** — R4 moved last window, so the「zero for two
consecutive critic laps」direction finding does not fire. Checked on disk at `c37f27e`, not read from
the laps that claimed it:

- **R9 stays ☐, and this lap answers the question WFG-036 v1 put to the critic** rather than inheriting
  it. The v1 document asks whether R9 requires a **committed** payload. It does not: the line's own
  words are 「`make finals-bundle` rebuilds it byte-identically」, which presupposes a build, not a
  second copy in the tree. I ran it in this fresh sandbox — `OK — release/kcf-finals-2026/ rebuilt
  byte-identically, 16 files`, exit 0 — so the mechanism the line names works. R9 is ☐ for the two
  things the line also names and the bundle does not have: the printables (R7 / WFG-007) and the booth
  recipe the run steps stand in for (WFG-037). The generated payload is not what is holding it.
- **R4 holds its tick and takes a second defect on it**, recorded the way WFG-067 and WFG-095 were.
  WFG-095 is closed and I re-checked it: every **[버림]** marker now sits on a sentence that carries its
  own number, and §1's rule says so. The new defect is the budget those markers are spent against
  (**WFG-100**): measured over the spoken blockquotes only, the six segments hold 1,630 syllables
  against 300 s — 5.43 per second sustained — and the implied rate runs 4.24 (3막, 75 s) to 7.07
  (마무리, 45 s). The segment that must be spoken fastest is the limitations close, and it is last.
  The tick was for a document that exists and whose numbers verify; both still hold.
- **A correction this file owes the loop.** Critics #14 and #15 wrote 「nothing in this window touched
  `web/`, twelfth / thirteenth consecutive window」. `git log -- web/` in this fresh clone says
  otherwise: `web/finals.html` was changed at **`deeb147`, 2026-09-04T15:32Z** — one line, the commit
  stamp that closed WFG-067 — about four critic windows before #15, not thirteen. The sentence those
  laps meant is true and is the one to write from now on: the screen's **content** has not changed
  since `dc63a06`, 2026-09-04T07:14Z. Left as a correction rather than an edit of their text (§3.7).

Previous count: **critic #15, 2026-09-05T0200Z: 4 of 11 (R2, R4, R5, R6). R4 is ticked that lap and
it is the first line to move in SIX critic laps.** Checked on disk at `43710f7`, not read from the
lap that claimed it: `docs/auto/DEMO_SCRIPT_5MIN.md` EXISTS (231 lines, Korean, DRAFT-labelled),
and I verified its three testable halves myself rather than trusting `tests/test_demo_script_5min.py`
— the six segment lengths sum to exactly 300 s and every cumulative bracket is consistent with them;
the §2 table carries one interruption sentence for each of the five judge lenses the routine scores
against; and all **33 registry keys** in the §3 mapping table resolve in `docs/NUMBERS.json` with
values matching the spoken text (`0.1939`, `79.23`, `24.73`, `9.17`, `15.14`, `23.67`, `26.594`→26.6,
`3.6`, `0.138`, `0.0867`, `0.0197`, `2218`, `20`, `24`, `0`, `0.89`, `0.107` and the rest). The two
screen sentences the script tells the student to quote verbatim are in the built `web/finals.html`.
**Still MISSING at HEAD:** `docs/auto/finals/BOOTH_SETUP.md` (R3 booth half, WFG-037),
`release/kcf-finals-2026/` (R9, WFG-036), no printable under `docs/auto/finals/` (R7, WFG-007).
`web/` was not touched in this window (thirteenth consecutive window), so R1 could not move.
⚠ One defect recorded **on** the newly ticked line and not enough to withhold it, exactly as
WFG-067 was recorded on R2: the script's **[버림]** droppable markers in 2막 and 3막 sit on
caveat-only sentences whose claims stay behind (WFG-095), and deleting either is uncaught by every
claim gate in the tree. That is this lap's one `fix-before-next-row` item.

Previous count: **critic #14, 2026-09-04T2300Z: 3 of 11 (R2, R5, R6), and no line has been ticked
for FIVE consecutive critic laps.** Checked on disk at `ed35f0d`, not read from the last lap
that claimed it: `docs/auto/DEMO_SCRIPT_5MIN.md` MISSING (R4), `docs/auto/finals/BOOTH_SETUP.md`
MISSING (R3 booth half), `release/kcf-finals-2026/` MISSING (R9), `docs/auto/finals/` still
holds one card and one screenshot folder and no printable (R7). Ticked **inside** the 24 h
window: exactly one, R2 by critic #8 at `12bf2d9` (0750Z), fifteen hours ago. Nothing in this
window touched `web/` — twelfth consecutive window — so R1 could not have moved either. The
loop-direction half of that is already filed (WFG-084, NH-024) and critic #14 adds one thing
the earlier laps did not have: **NH-021 is now satisfied**, WFG-062 is `done(e350571)`, and the
next `todo` row in table order is WFG-003, which ticks R4 and half of R1. There is no longer a
gate row, an escalation or a critic item standing between the loop and this checklist. The one
`fix-before-next-row` item this lap sets (WFG-087) is fifteen minutes on the Q&A bank.

Previous count: **critic #13, 2026-09-04T2000Z: 3 of 11 (R2, R5, R6), and no line has been ticked
for four consecutive critic laps.** The last tick was R2 by critic #8 at `12bf2d9` (0750Z);
critics #9, #10, #11 and #12 each added evidence to lines already ticked or already open, and
critic #12 did not write this file at all. Checked on disk this lap: `docs/auto/DEMO_SCRIPT_5MIN.md`
MISSING (R4), `docs/auto/finals/BOOTH_SETUP.md` MISSING (R3 booth half), `release/kcf-finals-2026/`
MISSING (R9), no printables under `docs/auto/finals/` (R7, the directory holds one card and one
screenshot folder). Under the routine's own rule that is a finding about the loop's direction and
not about the product; it is the reason **NH-024** is open and the reason this critic set **no
`fix-before-next-row` item**, so the next dev lap owes the critic nothing.

| # | ready when | evidence | status |
|---|---|---|---|
| R1 | `web/finals.html` opens from `file://` with Wi-Fi off, all four acts advance, every on-screen number maps to a `docs/NUMBERS.json` key (mapping table committed) |  **2026-09-05T1700Z (critic #20), a second defect on this line and NOT a tick:** beyond WFG-110's six unmapped keys, the 검증 레지스트리 evidence card prints 「built at commit 41498ef」 (`web/finals.html:1924`) and `git merge-base --is-ancestor 41498ef HEAD` **exits non-zero** — the object is reachable only from `origin/auto/lap-b1989d5-superseded` and `origin/ordering-boundary`. `tests/test_finals_screen.py` gates the other stamp (`_payload()["git"]`, `:544`/`:550`/`:649`) and never reads this field. WFG-115. | ☐ |
| R2 | The finals screen shows the evidence cards that exist today: operating point (WFG-019), reconciliation (WFG-018), detection floor (WFG-021), horizon grounding, refuge placement; rebuilt with `--verify` | **Detection-floor card written, screen not yet rebuilt (2026-09-03T2217Z dev lap).** WFG-047 released the stranded row and WFG-021 (a) shipped: `docs/auto/finals/DETECTION_FLOOR_CARD.md` states Session 19 with a registry key on every figure, `tests/test_detection_floor_card.py` (17) fails if any digit drifts from `docs/NUMBERS.json` or is attributed to the wrong fire, and `JUDGE_QA.md` Q10a/Q10b answer the 영덕-exclusion and false-alarm questions from it. Part (b) landed at `f5f8498`. **Still ☐:** nothing in `web/` has changed — putting this card and the other four onto the screen is WFG-017, and only that rebuild ticks R2  **Critic #6, 2026-09-04: the one finished card is now itself a finding.** `docs/auto/finals/DETECTION_FLOOR_CARD.md` opens 「위성은 사람보다 느렸습니다」 and this project's own `paper/manuscript.md` §4.7 says the measurement cannot say that; the manifest the delays are measured from calls the reference field the ignition. **F27 cleared 2026-09-04T0419Z (WFG-053).** The card's front sentence is now the size floor, the reference clock is named as the 기록된 발생일시 with the manifest's `provenance only` sentence quoted beside it, and the interim 99 % 목격신고 statistic was removed from the card after this lap's reviewer showed it is an unregistered year-to-date tally (CHARTER §3.3, §3.5b). **The card's text is correct today, verified line by line.** ⚠ But the gate written with it is a string tripwire, and the same reviewer escaped it repeatedly with reworded sentences (see that test's docstring for the verified-uncaught list). So WFG-017 may proceed on the card **as it now reads**, and whoever rebuilt the screen had to read the panel text rather than trust a green suite. **R2 TICKED by critic #8 at `12bf2d9`, 2026-09-04T0750Z.** All five cards are on the screen and critic #8 opened the committed screenshots to check: `5_card_operating.png` (운영점, pooled 0.138 with the three folds that have no true positive and their positive-cell counts), `6_card_detection.png` (탐지 바닥, 0.08~0.69 ha as a range with the flame-temperature caveat), `7_card_horizon.png` (240분 지평), `8_card_refuge.png` (대피 지점 배치, 20 → 24, and the claim narrowed to the one node actually re-verified), `9_card_reconciliation.png` (제출본과 정본, printing no retired value). `build_finals.py --verify` ran the three gates and the RELIABILITY tab prints their exit codes. `docs/finals_screen_v2.md` (219 lines) says for every card what it does NOT say, and the 탐지 바닥 card ships WFG-063's fix **before** the fix reached the three documents that still carry the old claim. ⚠ One defect on the ticked line, filed as WFG-067 and not enough to withhold the tick: the SYSTEM INTEGRITY panel prints `commit a562045`, which no longer exists after the lap's rebase. The durable claim gate is still WFG-062. **Critic #9, 2026-09-04: the tick holds and the defect is unchanged.** Nothing in this window touched `web/`; `git cat-file -t a562045` still answers `fatal: Not a valid object name` and `web/finals.html` still carries `"git":"a562045"`, so WFG-067 is open for a second window on a ☑ line. One thing did improve on the screen's behalf without the screen moving: the 탐지 바닥 card's sentence, which the screen shipped first and alone, is now the sentence in all four markdown surfaces too, and `tests/test_detection_ordering_is_not_claimed.py` reads the built `web/finals.html` as one of its five guarded files, so the screen is no longer the only correct document and is no longer ungated (WFG-063). ⚠ That gate's measured catch rate against a mutation set its author did not write is 2 of 20 (critic #9 F47), so the tick still rests on a lap having read the panel text, not on the suite. **Critic #10, 2026-09-04: the tick holds; WFG-067 is now in its third window on this ☑ line.** Nothing in this window touched `web/`. `git cat-file -t a562045` in this fresh clone still answers `fatal: Not a valid object name` and `web/finals.html` still carries `"git":"a562045"`. One thing worth recording against the tick rather than for it: `web/finals.html` is listed in the new `tests/test_external_figures_carry_their_scope.py` `GUARDED` tuple, and it prints two registered external figures (3,819동, 3,587명) that the gate's own two-entry `EXTERNAL_FIGURES` registry does not contain, so listing the screen there buys it nothing today (WFG-071). Coverage on this line is still a lap having looked at the panel.  **Critic #11, 2026-09-04: the tick holds; WFG-067 is now in its FOURTH window on this ☑ line.** Nothing in this window touched `web/`. `git cat-file -t a562045` in this fresh clone still answers `fatal: Not a valid object name` and `web/finals.html` still carries `"git":"a562045"`. The line of the panel whose entire job is to let a judge verify the build has now named a commit that does not exist for four consecutive critic laps, against a fix that is one rebuild plus a one-line `git cat-file -e` gate. Coverage on this line is still a lap having looked at the panel text. | ☑ |
| R3 | `make all-checks` green on a clean clone (CI) and on the booth laptop recipe in `docs/auto/finals/BOOTH_SETUP.md` | **The F13 red is repaired at `509819d`** (the lineage annotation the critic specified). `gates.py --mode full` was RED at `633c3db` — this lap's own WFG-048 row was the first document to cite `data/processed/detection/firms_first_detection.json` and `check-artifact-manifest` fired; the manifest was rebuilt at `710d5b0` and the run there is ALL GREEN (`1188 passed, 56 skipped`), which is the head recorded in this lap's report. `--assert-head` refuses a push whose gates read a different commit, and it is what a lap should read before writing a line like this one. `baseline-verify` WARN is expected off-laptop and is a soft step. **Re-verified independently by critic #5 at `5a0466e` (2026-09-04T0147Z):** `gates.py --mode full` exits 0 in a fresh cloud sandbox (`1229 passed, 62 skipped`, 163 s), now including the new `check-readme-figures` step, so `auto/dev` is green at HEAD for the second consecutive critic lap. **Re-verified independently by critic #4 at `12b8ac7`:** `gates.py --mode full` exits 0 in a fresh sandbox (`1185 passed, 62 skipped`, collected 1247), so `auto/dev` is green at HEAD for the first time in four critic laps and `--assert-head` is what makes that structural. **Re-verified independently by critic #8 at `12bf2d9` (2026-09-04T0753Z):** `gates.py --mode full` exits 0 in a fresh cloud sandbox (`1273 passed, 62 skipped` in 204 s, **COLD**, against critic #7's cold `1261 / 62` at `8e0a6ad`: +12 passed, skips unchanged). `verify`, `snapshot-verify` and `env-check` PASS; `baseline-verify` WARN, expected off-laptop, `hard: false`, eighth window and still not a finding. Green at HEAD for a fifth consecutive critic lap. **Re-verified independently by critic #9 at `ce31b91` (2026-09-04T0950Z):** `gates.py --mode full` exits 0 in a fresh cloud sandbox (`1312 passed, 62 skipped` in 206 s, **COLD**, against critic #8's cold `1273 / 62` at `12bf2d9`: **+39 passed, skips unchanged**, like for like). `verify`, `snapshot-verify` and `env-check` PASS; `baseline-verify` WARN, expected off-laptop, `hard: false`, ninth window and still not a finding. `--assert-head` and `--assert-reported` both exit 0 at HEAD. Green at HEAD for a **sixth** consecutive critic lap. **Re-verified independently by critic #10 at `3a70e16` (2026-09-04T1200Z):** `gates.py --mode full` exits 0 in a fresh cloud sandbox (`1342 passed, 62 skipped` in 152 s, **COLD** — first full run in this sandbox, so the six SRTM-gated tests skipped, WFG-039 — against critic #9's cold `1312 / 62` at `ce31b91`: **+30 passed, skips unchanged**, like for like, fourth comparable window). `verify`, `snapshot-verify` and `env-check` PASS; `baseline-verify` WARN, expected off-laptop, `hard: false`, tenth window and still not a finding. `--assert-head` and `--assert-reported` both exit 0 at HEAD. Green at HEAD for a **seventh** consecutive critic lap. **Re-verified independently by critic #11 at `83f49bc` (2026-09-04T1400Z):** `gates.py --mode full` exits 0 in a fresh cloud sandbox (`1367 passed, 62 skipped` in 196 s, **COLD** — first full run in this sandbox, so the six SRTM-gated tests skipped, WFG-039 — against critic #10's cold `1342 / 62` at `3a70e16`: **+25 passed, skips unchanged**, like for like, fifth comparable window). `verify`, `snapshot-verify` and `env-check` PASS; `baseline-verify` WARN, expected off-laptop, `hard: false`, eleventh window and still not a finding. Green at HEAD for an **eighth** consecutive critic lap. ⚠ And this is the window that shows what the sentence is worth: the suite was green, and one of its passing tests (`tests/test_juso_yeongdeok.py:11`) was asserting that 영덕's 시군구 code is 47920 over an artifact lying 45 km outside 영덕 (critic #11 F54, WFG-075/076, NH-022). Gate green means no gate disagreed, not that the tree is right. **Re-verified independently by critic #13 at `baf6962` (2026-09-04T2000Z):** `gates.py --mode full` exits 0 in a fresh cloud sandbox (`1377 passed, 62 skipped` in 178 s, **COLD** — first full run in this sandbox, so the six SRTM-gated tests skipped, WFG-039 — against critic #12's cold `1376 / 62` at `c65dc56`: **+1 passed, skips unchanged**, like for like, seventh comparable window). `verify`, `snapshot-verify` and `env-check` PASS; `baseline-verify` WARN, expected off-laptop, `hard: false`, thirteenth window and still not a finding. Green at HEAD for a **tenth** consecutive critic lap. ⚠ And this is the window that shows what the CI half of this line is worth, which the sandbox half cannot: `auto-gates` was **RED on `auto/dev` for six consecutive pushes** (runs 86–91, `201c554` through `e4a7304`) while every lap that pushed them read ALL GREEN in its own sandbox. One test, `tests/test_finals_screen.py::test_the_stamp_gate_is_graded_against_the_ways_a_stamp_goes_wrong`, built a probe commit with `git commit-tree` and inherited a committer identity the runner does not have. Fixed at `21b8740`; runs 92, 93 and 95 are `success` and run 95 is this head. The residue worth recording against this line rather than for it: the first red was 16:03Z and the fix 18:39Z, **2 h 36 min against CHARTER §4b's 「catch it within the hour」**, and the hourly ci-red routine's own run on it produced a report and no fix because a concurrent lap had landed the same repair first. **Re-verified independently by critic #14 at `ed35f0d` (2026-09-04T2300Z):** `gates.py --mode full` exits 0 in a fresh cloud sandbox (`1453 passed, 62 skipped` in 208.9 s, **COLD** — first full run in this sandbox, so the six SRTM-gated tests skipped, WFG-039 — against critic #13's cold `1377 / 62` at `baf6962`: **+76 passed, skips unchanged**, like for like, eighth comparable window and the largest single-window gain this line has recorded, all of it WFG-062's `tests/test_withdrawn_claims_registry.py`). `verify`, `snapshot-verify` and `env-check` PASS; `baseline-verify` WARN, expected off-laptop, `hard: false`, fourteenth window and still not a finding. `--assert-head` exits 0 at HEAD. Green at HEAD for an **eleventh** consecutive critic lap. The CI half also recovered: `auto-gates` runs 92, 93, 95, 96, 97, 98 and **99 (this head) are `success`** (94 cancelled by a superseding push), so the six-red episode of runs 86–91 is closed for a second consecutive window and no red run sits behind a green report here. **Re-verified independently by critic #15 at `43710f7` (2026-09-05T0206Z):** `gates.py --mode full` exits 0 in a fresh cloud sandbox (`1464 passed, 62 skipped` in 317.3 s, **COLD** — first full run here, so the six SRTM-gated tests skip, WFG-039 — against critic #14's cold `1453 / 62` at `ed35f0d`: **+11 passed, skips unchanged**, like for like, ninth comparable window). `verify`, `snapshot-verify` and `env-check` PASS; `baseline-verify` WARN, expected off-laptop, `hard: false`, fifteenth window and still not a finding. `--assert-head` and `--assert-reported` both exit 0 at HEAD. Green at HEAD for a **twelfth** consecutive critic lap. ⚠ The CI half went red twice inside this window and the reason is new: `auto-gates` runs **103 (`a2a2994`) and 104 (`c8124a8`) are `failure`**, and in both the **`gates` job passed and the new `promote` job failed** — the fast-forward of `Main` that CHARTER §4c introduced at `a2a2994` cannot run while `Main` is a protected branch requiring a pull-request review, which is an author action nobody had filed (now **NH-025**). Fixed at `b3244f8` by making a refused fast-forward a warning rather than a red run, 20 minutes after the first red, well inside CHARTER §4b's hour. Runs 105, 106 and **107 (this head) are `success`**. Recorded here because it changes what a red `auto-gates` run means on this line: from 09-05 a red run can be a promotion refusal with green gates behind it, and a lap must read the **job**, not the run. **2026-09-05T1217Z (WFG-037), a note and NOT a tick — the dev lap does not tick, the critic does (CHARTER §10).** `docs/auto/finals/BOOTH_SETUP.md` now exists, so the sentence above it is history. ⚠ And writing it falsified this line's own command: **`make all-checks` does not pass, and not only off-laptop.** It aborts at `baseline-verify` with six differences against the freeze at `89730db89921`, of which only two are the missing `data/raw/firms_data/` manifests; the other four — the registry entry count and three tracked `pace_*.json` artifacts — are in every clone and will abort the same command on the author's laptop. `gates.py` treats the step as soft (`hard: false`), which is why eighteen windows of 「WARN, expected off-laptop」 read past it. The re-freeze needs the raw bundle and is the author's (**NH-029**); the recipe's §1.1 sends the booth morning to `gates.py --mode full` instead. **So the CI half of this line is unchanged and green; the booth half now has a written recipe whose every command was executed and whose own readiness command is the one that fails.** The rehearsal half is R12 / NH-014 | ☐ |
| R4 | A 5-minute demo script in Korean with per-act timings and the sentence for each judge type's interruption (`docs/auto/DEMO_SCRIPT_5MIN.md`) | **The file exists as of the 20260905T0025Z dev lap (WFG-003).** Korean, DRAFT-labelled per CHARTER §9, six timed segments summing to exactly 300 s over `docs/FINALS_DEMO.md`'s four acts plus an opening and a limits close, one interruption sentence for each of the five judge lenses, and a §3 mapping table of 35 rows (23 화면 / 12 구두) each carrying a registry key or a named artifact, where 화면 means a card in scripts/finals.template.html actually renders it (not merely that the key sits in the built page). `tests/test_demo_script_5min.py` (9) reads that table mechanically and was graded 6 of 6 against mutations written to break it. **The dev lap does not tick this line — the critic does (CHARTER §10)**, and the half a test cannot reach is whether five minutes of Korean fits in five minutes: the segment times are design values, not a rehearsal, and §5 of the document says so. R12/NH-014 is where a human reads it aloud. **R4 TICKED by critic #15 at `43710f7`, 2026-09-05T0200Z**, on the independent check recorded in the header above: 300 s exactly, five lenses, 33 registry keys resolved and value-matched by hand, two quoted screen sentences found in the built page. The half a test cannot reach is unchanged and the tick does not claim it — five minutes of spoken Korean fitting in five minutes is R12/NH-014, and §5 of the document says so in the document. ⚠ Defect carried on the ticked line: WFG-095, the **[버림]** markers on caveat-only sentences in 2막 and 3막 — **closed at `9345848`**. **2026-09-05T0625Z (WFG-100), correcting this cell rather than the tick (CHARTER §10 — the dev lap does not tick):** the sentence above saying 「the segment times are design values」 is no longer true. They are now a *measurement* — 1,684 spoken syllables allocated over 300 s at one rate of 5.61 syl/s, giving 29 / 44 / 50 / 60 / 59 / 58 s where the design values were 25 / 45 / 55 / 75 / 55 / 45 and implied six different rates spanning 1.62× (`docs/demo_script_pace.md`, `data/processed/demo_script_pace/pace_20260905T0625Z.json`, `tests/test_demo_script_pace.py`). **The half a test cannot reach is unchanged and this note does not claim it:** whether that rate is sayable is still R12 / NH-014, a human with a stopwatch. The critic owns whether the tick survives the re-budget. | ☑ |
| R5 | Judge Q&A bank v2 complete: every T0 answer cites a file; no purged phrasing remains (`tests/test_judge_qa_bank.py` green) | Invariants met: `docs/auto/JUDGE_QA.md` 33 questions, tiers 14/13/6, 18 tests green in `gates.py --mode full` at `1113388`, WFG-002 `done(20260903T1536Z)`. **Tickable at `1c1561e` (2026-09-03T2017Z dev lap):** the §0 bullet that told the student the repository was wrong about "6 → 34" (the 폐기된 452계열 bracket; canonical is 6 → 66) is rewritten onto `docs/ssot_audit_2026-09-03.md` §1 and now tells the student explicitly NOT to say 오타 at the booth. CRITIC F1 `done(1c1561e)`. `tests/test_judge_qa_bank.py` 18 passed, `check_forbidden` and `tests/test_rescue_lineage_ssot.py` green on the rewritten text | ☑ |
| R6 | 제출본 대비 정본 reconciliation sheet exists, in Korean, one page, and JUDGE_QA links to it | `docs/submission_reconciliation.md` (Korean, 11 rows, spoken lines); `JUDGE_QA.md:34` links to it; WFG-018 `done(20260903T0653Z)`; row 8 corrected by WFG-004 at `6a2c8a3` | ☑ |
| R7 | Printables as PDF under `docs/auto/finals/`: evidence sheet (A4), reconciliation sheet, related-work and SFTD059T differentiation panel, booth checklist, 29 dispatch sheets sample |  **2026-09-05T1700Z (critic #20):** still nothing. `docs/auto/finals/` holds two `.md` files and one screenshot folder and no PDF, on the sixth day this line has been held by a row no lap has claimed. Critic #19's falsifiable test resolved (WFG-109 closed, printables absent), so **WFG-007 is raised P1 -> P0** and is second on `docs/auto/DIRECTION.md`. The printing and the poster stay the student's; the files and the build script are the agent's and are what P0 buys. | ☐ |
| R8 | `README.md` has a Round-4 section and the English abstract draft; forbidden-string and collision gates green | **Sourcing half now durable, 2026-09-04 (critic #5).** Every figure the opening paragraph prints was re-opened at its primary page this lap and every one holds (경상북도 보도자료: 99,289 ha / 149시간 / 3,819동 / 2,246세대 3,587명 / 1조 505억, and the 「1986년 이래 역대 최대 피해 면적」 superlative carried by that release itself; 산림청 2025-05-16 for 347건 / 104,788 ha over 봄철 산불조심기간 1.24~5.15). `data/processed/external/fire_2025_scale.json` + 16 `fire2025_*` registry keys + `check-readme-figures` + 44 new tests mean the figures can no longer be rewritten silently. **(b) is CLOSED at `e5aaaa7`/`28b4c38`, verified by critic #6 at `b855943`:** the 「약 43 %」 / 「about 43 %」 sentence is gone from both languages, `README.md` prints no share at all, and the tripwire now scans both whole paragraphs instead of the one line that carried `104,788`. **Still not tickable on (a) alone:** no Round-4 section and no abstract draft yet (WFG-010). Previously: **Still not tickable, for two reasons:** (a) no Round-4 section and no abstract draft yet (WFG-010), and (b) the scope note's 「about 43 %」 sentence at `README.md:210-211` / `:528` is false and contradicts this repository's own `fire2025_chain_share_of_nationwide_pct = 94.8` (critic #5 F21). Previously: **Half recovered, 2026-09-04.** The falsifiable-in-one-search half is fixed by two laps: the 0037Z manual lap rewrote both opening paragraphs onto 99,289 ha, and the 0017Z dev lap sourced every figure to a URL it opened, corrected the nationwide comparison's **period** (봄철 산불조심기간 2025-01-24~05-15, not March) against the 산림청 release, withdrew the 95 % share claim as basis-mixing, and added `tests/test_motivating_event_figures.py` — the gate these figures never had. **Still not tickable:** no Round-4 section and no abstract draft yet (WFG-010), which is the other half of this line. Original finding: **Moved backwards this window.** No Round-4 section and no abstract draft yet, and `12b8ac7` rewrote the existing opening paragraph in both languages to figures that are wrong: 45,157 ha for a chain that burned 99,289 ha, and 영덕 8명 against this repository's own correction to 10 (critic #4 F16/F17, WFG-043). The gates are green because none of these figures has a registry key, which is the point of WFG-049. This line cannot be ticked while the paragraph above the Round-4 section is falsifiable in one search | ☐ |
| R9 | The release bundle `release/kcf-finals-2026/` (WFG-036) exists: `web/` whole, printables, `README_KO.md` with the 10-line run recipe, `CITATION.cff`, and `make finals-bundle` rebuilds it byte-identically | **v1 landed 2026-09-05 (WFG-036, dev lap 20260905T0355Z), and the dev lap does not tick this line — the critic does (CHARTER §10).** `release/kcf-finals-2026/` holds the four screens (`finals`, `console`, `field_view`, `refuge_placement`), the fonts and poster, `LICENSE`, `CITATION.cff`, a ten-step Korean `README_KO.md` and `MANIFEST.json`. `make finals-bundle` re-assembles the folder, re-derives every SHA-256 and exits non-zero naming any file the committed manifest does not describe; `tests/test_finals_bundle.py` (7) hashes the sources independently of the builder. ⚠ **Two things this v1 does not have, and they are why it is not tickable yet:** the printables the line names (R7 / WFG-007 — none exist), and the booth recipe the run steps stand in for (WFG-037). ⚠ The payload (`web/`, `CITATION.cff`, `LICENSE` inside the bundle) is **generated and git-ignored**, so a clean clone holds only `README_KO.md` and `MANIFEST.json` until the command is run once; the reasoning is in `docs/finals_bundle.md` and a critic who reads R9 as requiring a committed payload should say so rather than inherit the choice. **Answered by critic #16, 2026-09-05: R9 does NOT require a committed payload.** The line's own condition is that `make finals-bundle` rebuilds it byte-identically, which presupposes a build; I ran it in a fresh cloud sandbox and it exits 0 with `OK — release/kcf-finals-2026/ rebuilt byte-identically, 16 files`. The choice is accepted and is not what holds the line. **Still ☐ for exactly two things the line also names:** the printables (R7 / WFG-007) and the booth recipe (WFG-037), which is why WFG-037 was moved directly under WFG-036 in the table this lap. **2026-09-05T1217Z (WFG-037), a note and NOT a tick:** the booth recipe half is now written, and the bundle gained a seventeenth file — `check_bundle_copy.py`, which verifies a COPY of the folder against the manifest that travels with it, reads and never writes, and imports nothing outside the standard library so a borrowed machine with no repository can run it. It exists because this line's mechanism was found to answer a different question than the booth asks: `make finals-bundle` overwrites the bundle from the tree before hashing, so a file corrupted **on the stick** is repaired rather than reported (measured by appending seven bytes to the bundle's `finals.html`: the run printed `OK`), and the builder never enumerates the folder, so a file an earlier run left behind ships on the stick while the run reports byte-identity (**WFG-108**). The line still waits on the printables (R7 / WFG-007) | ☐ |
| R10 | ~~AI ledger~~ **Withdrawn 2026-09-04.** The organisers confirmed to the author that no AI-disclosure artifact is required (NH-008), and `AI_DISCLOSURE.md` was removed at the author's instruction. `ROUTINE_PROMPTS.md` and the `Co-Authored-By` trailers remain under CHARTER §9 as booth-explainability practice, not as a compliance artifact | Withdrawn, not failed | — |
| R11 | `docs/HANDOFF_ROUND3.md` §5.1 and every date in `docs/auto/` say `auto/dev`, 10-16 and 10-24 | The three live lines CRITIC F7 named are fixed at `1c1561e`: `CHARTER.md:11` and `RUBRIC.md:20` now read 10-24, and NH-006's question text is annotated as a superseded record rather than edited (§3.7). The `research/sweeps_2026-09-03/*` files and the two BACKLOG rows that quote the 10.18-vs-10.24 question predate or describe the NH-006 decision and keep their text as dated records. **Still ☐ for the branch half only:** `docs/HANDOFF_ROUND3.md:898` states "All work stays on `round3-dev`", which is WFG-024 and blocked on WFG-023 | ☐ |
| R12 | The author has run the booth recipe on the actual laptop once and closed NH-014 | | ☐ (author) |
