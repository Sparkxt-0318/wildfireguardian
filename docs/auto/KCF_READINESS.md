# KCF readiness — the final product's definition of done

The critic lap ticks every line daily with a commit or file as evidence, in the
`evidence` column; an unticked line is a finding, and the product is not ready
until every line is ticked. The dev laps work WFG-036 until it is. Dates: freeze
2026-10-16, finals 2026-10-24 (김대중컨벤션센터, Gwangju, offline booth).

**Tick count, critic #29, 2026-09-06T2015Z: 4 of 11 (R2, R4, R5, R6), unchanged for a SIXTH consecutive
critic lap — and this is the first of those six windows that contained no dev lap at all, so the count
could not have moved.** Checked on disk at `1b26c3a`, re-run rather than read, on a clone fully unshallowed
(`git rev-parse --is-shallow-repository` answers `false`, 500 commits).

- **Why the zero is not a direction finding this time, stated before anything else.** `git diff
  e95fe28..1b26c3a` changes **zero lines outside `docs/auto/`**. The 18:17Z slot was ceded to the research
  routine (CHARTER §14, `LOOP_CONFIG.json` -> `research_cadence_note`, the author's 2026-09-04 decision),
  so the window holds one critic report and one research lap and nothing else. A window with no dev lap
  cannot tick a readiness line, and reading that as a failure of direction would be a false reading. The
  routine's rule (zero across two consecutive laps is a direction finding) is therefore **recorded and not
  fired**; the measurement went to **NH-038**, which asks the author this exact question and now carries a
  sixth data point. The mechanism the window exposed is **WFG-145**.
- **R3 sandbox half green; CI half clean; and the cold count is unchanged, which is the correct result.**
  `gates.py --mode full` is **ALL GREEN** at `1b26c3a`: `1599 passed, 62 skipped`, cold, 273.6 s — **identical**
  to critic #28's cold `1599 / 62` at `e95fe28`, like for like, which is what a window with no code in it
  should produce. `verify`, `snapshot-verify` and `env-check` PASS; `baseline-verify` WARN is CHARTER §3d
  information. Read through the GitHub MCP (WFG-119 records the `curl` 403): `auto-gates` runs **161 to 180**
  on `auto/dev` are **17 `success` and 3 `cancelled`** (`dfdf480`, `828bbae`, `ef61e9b`, each superseded by a
  green push), with **no `failure` at all**, so there is no gate finding and no CHARTER §4b finding this lap.
  Run 180 at `1b26c3a`, this head, is `success`. `--assert-head` exits 0. Every **dev** report in the window
  carries `Reviewed by:`. ⚠ The one report in the window that carries no such line is the research lap's
  (`2026-09-06T1838Z-research.md`), which is a gap in the routine's prompt rather than a missing practice —
  **WFG-147**. R3 still waits on one `make all-checks` run on the author's laptop, and WFG-139's network
  test is unchanged and untaken.
- **R7 does not tick, and the kit has drifted a THIRD time — written by critic #28's own commit.** I
  re-hashed all four manifest `SOURCES` against the tree here in one process: `BOOTH_SETUP.md`
  `ef7342dacf…`, `DEMO_SCRIPT_5MIN.md` `b1aae78f35…` and `DETECTION_FLOOR_CARD.md` `84648d4d6e…` all
  **match**; `docs/auto/JUDGE_QA.md` manifest `2c8451211e5f97…` against tree **`175da9e50c5ce9…`**. The PDF's
  own sha256 still matches its manifest, so `tests/test_printables.py` stays fully green over it. The series
  on that one file is `af955a30fa…` (#27) -> `7d5ac4c9c5…` (#28) -> `175da9e50c…` (here), and **all three
  drifts were correction notes written by critic or dev laps, not judge-facing improvements** — #27's Q35
  note at `a64b904`, the WFG-133 lap at `923ffbd`/`32de531`, and critic #28's own `050731a`. This lap adds a
  fourth for the same reason and does not exempt itself. **That is this report's root objection**, because
  `WFG-144`'s cell now sequences a genuinely new judge-facing card behind the rebuild 「or the printed 17
  pages go stale a fourth time」, while the laps making that argument spend the same freshness on themselves.
  WFG-134 rebuilds, **WFG-140** is the gate, and the gate is the half that dissolves the sequencing argument.
- **R8 does not tick and its defect is one clause wider than critic #28 measured.** `README.md:22-26` is
  unchanged and still says 42 of 458 reach a refuge 「**only** when the router accounts for where the fire
  **will be**」, so **WFG-138** is `todo` — but the item was never in front of a dev lap (see the first
  bullet), so critic #28's falsifiable test on it **could not be run and I do not report its verdict**. What
  the judge drill added: `docs/auto/JUDGE_QA.md` **Q19**'s draft answer carries 「영덕에서 458개 원점 중 **42**개,
  의성·안동에서 368개 중 **91**개가 시간 인지 경로에서만 …」, and the ⚠ block directly beneath it corrects the
  **91** and leaves the **42** untouched in the same sentence. Both come from the same fire-blind control
  (`src/wildfireguardian/routing/evacuation.py:270`); 영덕 needs the caveat **more**, because the
  present-perimeter opponent has only ever been run on 의성·안동
  (`data/processed/present_perimeter_arm_uiseong_andong_2025.json`). A dated ⚠⚠ note with the sentence to say
  is on Q19 at this head and 50 judge-qa, printables and fair-opponent tests are green over it. WFG-138 is
  widened by that half and **carried forward** as this lap's one item rather than re-filed.
- **R5 keeps its tick.** The bank gained one correction note and no card changed its answer; the drill's
  finding is R8's, above. ⚠ The bank still has **no card** for 「산림청·경기도가 이미 산불확산예측을 하고 있는데
  무엇이 다릅니까?」 (**WFG-144**, P1), which is the most likely question a disaster-response judge asks, and
  the research lap's own page says that if the author promotes one row it is that one.
- **R1, R2, R4, R6, R9, R11 unchanged**; R10 stays withdrawn and R12 is the author's. I did not re-measure
  WFG-110's six registry keys and do not tick on a number I did not take.
- **Sourcing re-checked rather than accepted**, because the window's only substantive prose is a new
  landscape note whose sources no gate can read. I re-opened both live URLs: 경향신문 (G-DAPS) confirms the
  date, the 30-minute steps, the 읍면동 unit, the **589** alert facilities, the following-month trial, and
  **no accuracy figure**; 사이언스타임즈 confirms every NIFoS figure the note quotes. **One error: the note
  dates that article 2026-02-12 and the page says 2026-02-13** — one character, filed as **WFG-146** because
  CHARTER §3 rule 5b makes the date part of what licenses the figure.

**Tick count, critic #28, 2026-09-06T1736Z: 4 of 11 (R2, R4, R5, R6), unchanged for a FIFTH consecutive
critic lap — and this lap's finding is that one of the ticked-adjacent claims, the one about running on a
clean clone, is false.** Checked on disk at `e95fe28`, re-run rather than read, on a clone **fully
unshallowed** (`git rev-parse --is-shallow-repository` answers `false`, 496 commits).

- **R3 is the line this lap moves against, and it does not lose its half-green so much as change what the
  green means.** `gates.py --mode full` is **ALL GREEN** at `e95fe28`: `1599 passed, 62 skipped`, cold,
  288.4 s (critic #27's cold `1569 / 62`: **+30 passed**, skips unchanged). `verify`, `snapshot-verify`,
  `env-check` PASS; `baseline-verify` WARN is CHARTER §3d information. CI half clean: read through the
  GitHub MCP (WFG-119 records the `curl` 403), `auto-gates` runs **#154 to #178** on `auto/dev` are **21 <!-- forbidden-ok: 154 -->
  `success` and 4 `cancelled`**, **no `failure` at all**, so there is no gate finding and no CHARTER §4b
  finding this lap. Run 178 at `e95fe28`, this head, is `success`. `--assert-head` and `--assert-reported`
  both exit 0, and every dev report in the window carries `Reviewed by:`. ⚠⚠ **What is new is that the
  clean-clone run is not clean.** On a clone created at 16:57Z with no `data/raw/` at all, the gate run
  wrote `data/raw/dem/srtm/N36E129.hgt` (**25,934,402 bytes**) at 17:02Z, fetched from
  `elevation-tiles-prod.s3.amazonaws.com` by `tests/test_spread_warmup.py:156`, which passes
  `dem_source="srtm"` with no skip guard. `docs/clean_clone_gates.md:27` reads 「No network, no keys, no
  `.env`.」 and is one of the three files `docs/auto/JUDGE_QA.md` **Q28** cites to a judge. CHARTER §4b:
  「No test may depend on the local clock, the timezone, the network, or files outside the repository.」
  **WFG-139.** Six tests keyed on that tile (`test_srtm_dem.py:81/:94/:109/:170`,
  `test_validation_robustness.py:57`, `test_validation_session3.py:171`) are `skipif`-guarded and `skipif`
  is evaluated at collection, so on every fresh CI clone the download always lands after the decision to
  skip: **those six have never run in CI.** They are the terrain-plausibility checks (ocean clipped to 0 m,
  max elevation at least 400 m, east strip lower than west) on the DEM the router walks over. This is also
  the whole of the cold/warm split the loop has diagnosed twice and never chased: cold `1599 / 62`, warm
  `1605 / 56`, same commit, both measured here, delta exactly those six. R3 keeps its sandbox half-green
  because the suite does pass; what it can no longer be read as is evidence that a stranger with no network
  gets the same answer.
- **R7 does not tick and the kit is staler than critic #27 left it.** I re-hashed all four manifest sources
  against the tree at `e95fe28`: `BOOTH_SETUP.md`, `DEMO_SCRIPT_5MIN.md` and `DETECTION_FLOOR_CARD.md`
  match; `docs/auto/JUDGE_QA.md` does not, and the tree hash has moved again — manifest `2c8451211e…`,
  tree **`7d5ac4c9c5…`** where critic #27 measured `af955a30fa…`, because the WFG-133 lap edited Q35 after
  that measurement. So the printed 17 Q&A pages carry the pre-WFG-117 Q30 **and** Q35's ⚠ block with **no**
  retraction on it, since critic #27's ⚠⚠ note landed at `a64b904`, after the `3e92b69` build. Critic #27
  pre-registered this branch: if any source is still stale, file the gate separately. Done — **WFG-140**.
  WFG-130 and WFG-134 keep the rebuild.
- **R8 does not tick and takes a new defect that is worse than staleness.** `README.md:22-26` asserts that
  42 of 458 origins reach a refuge 「**only** when the router accounts for where the fire **will be**」.
  `paper/manuscript.md`'s Abstract carries the same two numbers and then says the contrast 「does not
  separate knowing where the fire will be from knowing where it is」, because the baseline is fire-blind
  (`src/wildfireguardian/routing/evacuation.py:270`). `paper/GAPS.md` G7 records that the abstract was
  corrected for exactly this, and names the booth script (WFG-103) and the finals template (WFG-109) as the
  two surfaces already repaired. The README is the fourth and was never touched. **WFG-138**, and it is this
  lap's one `fix-before-next-row` item.
- **R1, R2, R4, R5, R6, R9, R11 unchanged**; R10 stays withdrawn and R12 is the author's.
- **Zero ticks for a FIFTH consecutive critic lap, and this time I do not think the direction is right.**
  Critics #26 and #27 each read the same count and concluded the window had done its one item well, which
  was true both times. What the fifth reading exposes is the mechanism rather than any lap: the last three
  dev laps each built a critic's `fix-before-next-row` item, all three on documents the loop wrote, and
  nothing has finished the booth kit since it landed at `3e92b69` on 09-06 at 06:20Z. The sprint plan names
  09-11 for the printables and 09-10 for the bundle. The cap of one item per critic lap is also a floor of
  one, and it is a cap on the number of items rather than on their cost. That is **NH-038**, and I am asking
  the author rather than widening the rule myself, because §14b is the author's steer.

**Tick count, critic #27, 2026-09-06T1400Z: 4 of 11 (R2, R4, R5, R6), unchanged — and this lap's finding is
that the surface a line is ticked on and the surface a human meets are not the same object.** Checked on
disk at `dd500e6`, re-run rather than read from a report, on a clone **fully unshallowed**
(`git rev-parse --is-shallow-repository` answers `false`, 488 commits), which is the control the last seven
laps on this page did not have.

- **R1 is unchanged and waits on WFG-110's six unmapped registry keys alone.** The `41498ef` half stays
  **withdrawn** and is now verified with the instrument rather than around it: on the unshallowed clone
  `git merge-base --is-ancestor 41498ef HEAD` exits **0**, `git rev-list --count 41498ef..HEAD` answers
  **283** (critic #26's 277 plus this window's six commits, so the two measurements agree), and
  `git branch -a --contains 41498ef` names `auto/dev`, `origin/auto/dev` and `origin/Main`. The counts half
  stays fixed: `web/finals.html` prints `n_entries` **383** / `n_reproducible` **325** against a registry
  holding 383 / 325 / 58-not, counted here in one process. I did not re-measure WFG-110's six and do not
  tick on a number I did not take.
- **R5 keeps its tick and takes a defect on it that is worse than the one it took last lap, because this
  one is a false statement rather than a stale one.** `docs/auto/JUDGE_QA.md` Q35 is **T1**, the
  reproducibility question. Its ⚠ block tells the student **not** to say the draft's true sentence
  「현재 브랜치에서 닿는 커밋입니다」 and to say instead 「레지스트리 카드의 각인은 … 지금 브랜치에서
  닿지 않습니다」. That is false at this head and at every head since the object was written. It also
  asserts the card prints **326** where the screen prints **383**. **Critic #26 withdrew that measurement
  in this very cell at 1100Z and wrote 「`JUDGE_QA.md` Q35 is correct as written and must not be edited」**,
  which is true of Q35's draft answer and false of the ⚠ block that overrides it; the effect was to protect
  the false half from repair for a full window. WFG-133, and it is this lap's one `fix-before-next-row`
  item. The tick survives on R5's literal condition (Q35 is T1, not T0; the bank's self-count is unchanged;
  `tests/test_judge_qa_bank.py` is 23 green inside the full run below) and a dated ⚠⚠ correction note with
  the measured table is on Q35 at this head so nobody rehearses the false block.
- **R7 does not tick and now has a second reason, which is about freshness rather than contents.**
  WFG-130 is unchanged: the kit contains one of the five printables R7 names and its manifest still says
  the reconciliation sheet 「does not exist yet」 while `docs/submission_reconciliation.md` is the file R6's
  own tick is written on. **New this lap: the kit is also stale.** I re-hashed all four sources against the
  tree. `BOOTH_SETUP.md`, `DEMO_SCRIPT_5MIN.md` and `DETECTION_FLOOR_CARD.md` match; `docs/auto/JUDGE_QA.md`
  does not — manifest `2c8451211e5f97eb…`, tree `af955a30fa500391…`. The PDF was built at `3e92b69` and
  WFG-117 rewrote Q30 at `fc05320`, so **the 17 printed Q&A pages carry the pre-WFG-117 Q30 with the
  「326 · 268」 warning this window removed, plus Q35's false block.** `tests/test_printables.py` checks
  that the manifest *has* a hash per source and that the PDF matches its own hash; nothing compares a
  recorded source hash against the tree, which is the one comparison that detects this. WFG-134.
- **R3 sandbox half green; CI half clean.** `gates.py --mode full` is **ALL GREEN** at `dd500e6`
  (`1569 passed, 62 skipped`, cold, 304.3 s, against critic #26's cold `1565 / 62`: **+4 passed**, skips
  unchanged). `verify`, `snapshot-verify`, `env-check` PASS; `baseline-verify` WARN is CHARTER §3d
  information. Read through the GitHub MCP (WFG-119 records the `curl` 403): the **25** most recent
  `auto-gates` runs on `auto/dev`, numbers **145 to 173**, are **22 `success` and 3 `cancelled`**
  (`828bbae`, `ef61e9b`, `9ebf5a5`, each superseded by a green push). **No `failure` at all, so there is no
  gate finding and no CHARTER §4b finding this lap.** Run 173 at `dd500e6`, this head, is `success`.
  `--assert-head` and `--assert-reported` both exit 0. Every dev report in the window carries
  `Reviewed by:`. ⚠ One small correction to critic #26's cell: it wrote that every *critic* report of the
  last 24 h carries `Reviewed by:` too, and `docs/auto/reports/2026-09-05T2330Z-critic.md` does not. Critic
  laps have no subagent reviewer by design, so this is a wrong sentence rather than a missing practice, and
  it is not a finding. R3 still waits on one `make all-checks` run on the author's laptop.
- **R2, R4, R6 hold. R8, R10, R11, R12 unchanged**, and R12 is the author's.
- **Zero ticks for a FOURTH consecutive critic lap, and the direction is still not what is wrong.** The
  window cleared critic #26's one item, cleared it well, and shipped a gate that did not exist. What the
  count exposes this time is narrower than last time and cheaper to fix: **the loop measures whether a
  correction was made, never whether it arrived.** Both of this lap's findings are one correction that
  reached the pages the loop reads and stopped at the surfaces a human meets — Q35's card, and the printed
  kit. That is WFG-133 and WFG-134, and the standing rule is now on `DIRECTION.md`: grep the judge-facing
  surfaces for the withdrawn string before writing 「withdrawn」 anywhere.

**Tick count, critic #26, 2026-09-06T1100Z: 4 of 11 (R2, R4, R5, R6), unchanged — and this lap's finding is
that one of the reasons R1 has been ☐ was never real.** Checked on disk at `b2bdaf0`, re-run rather than read
from a report, and on a clone **deepened to 300 commits with the depth recorded beside every claim**.

- **R1: two of its three recorded defects are gone, and the second one was never there.** The counts are
  fixed: `web/finals.html` prints `n_entries` **383** and `n_reproducible` **325**; `docs/NUMBERS.json`
  holds 383 entries, 325 reproducible, 58 not, counted here in one process. WFG-113 is `done(20260906T0920Z)`
  and this is critic #25's falsifiable-test branch (1): **the repair ran, and WFG-119's ten-hour clock is
  reset** — the screen's stamp is now `62b58e1`, **6** commits behind `HEAD` rather than 29.
- ⚠⚠ **The second defect on this line is WITHDRAWN, and it stood for five critic laps.** `41498ef` **is**
  an ancestor of `HEAD`. Measured here: `git merge-base --is-ancestor 41498ef HEAD` exits **0**,
  `git rev-list HEAD | grep -c 41498efbf0679276c140b3cbfc0819e5265e7733` answers **1**,
  `git rev-list --count 41498ef..HEAD` answers **277**, and `git branch -a --contains` names `auto/dev`,
  `origin/auto/dev` and `origin/Main`. The object sits **277** commits back. Critic #20 raised it in the
  default **depth-50** clone; critic #21 deepened by 120 and re-confirmed; critic #24 deepened to **250** and
  wrote 「so the shallow boundary is not the confounder」. **250 < 277, so it still was.** Critics #20, #21,
  #23, #24 and #25 each wrote 「re-run rather than read」 and each re-ran the same command inside the same
  short instrument. The withdrawal is on **WFG-115**, which drops P0 -> P1 and is re-scoped to the smaller
  defect that survives: the line is **stale by construction and mislabelled** (the registry held 153 entries
  at that commit and the card beside it prints 383), not unreachable. **`JUDGE_QA.md` Q35 is correct as
  written and must not be edited.** Nothing on the judged screen is wrong about reachability.
- **R1 stays ☐ on one thing only: WFG-110's six registry keys with no committed mapping table.** I did not
  re-measure that six this lap and do not tick on a number I did not take. R1 is now one row from tickable,
  which it has not been in twenty-six windows.
- **R5 keeps its tick and takes a defect on it, and the defect inverted inside one window.** `JUDGE_QA.md`
  Q30 is **T0**. Its ⚠⚠ block still tells the student the screen prints **326 · 268**, that pointing at the
  screen leads them to a stale number, and that three counts answer this question. **All three are false at
  this head.** A wrong warning survived a correct repair. WFG-117 is re-scoped, moved to position 2, and is
  this lap's one `fix-before-next-row` item; a dated correction note is on Q30 so the student does not
  rehearse the stale block. The tick survives: the bank's own self-count is unchanged and
  `tests/test_judge_qa_bank.py` is green inside the full run below.
- **R3 sandbox half green; CI half clean.** `gates.py --mode full` is **ALL GREEN** at `b2bdaf0`
  (`1565 passed, 62 skipped`, cold, 199.1 s, against critic #25's `1562 / 62`: **+3 passed**, skips
  unchanged). `verify`, `snapshot-verify`, `env-check` PASS; `baseline-verify` WARN is CHARTER §3d
  information. Read through the GitHub MCP (WFG-119 records the `curl` 403): the **25** most recent
  `auto-gates` runs on `auto/dev`, numbers **140 to 168**, span 2026-09-05T20:21Z to 2026-09-06T10:14Z and
  are **22 `success` and 3 `cancelled`** (`ef61e9b`, `9ebf5a5`, `785ba13`, each superseded by a later push
  that is green). **No `failure` at all, so there is no gate finding and no CHARTER §4b finding this lap.**
  Run 168 at `b2bdaf0`, this head, is `success`. `--assert-reported` exits 0 across the window and every
  dev, paper and critic report in the last 24 h carries `Reviewed by:` (the four without it are `manual`,
  the author's own laptop). R3 still waits on one `make all-checks` run on the author's laptop.
- **R7 and R9 unchanged, and WFG-130 is still the whole of what they wait on**, exactly as critic #25 left
  it: the printables PDF contains one of the five documents R7 names, and the build's manifest still says
  the reconciliation sheet 「does not exist yet」 while `docs/submission_reconciliation.md` is
  `done(20260903T0653Z)` and is the file R6's own tick is written on. Not re-litigated here.
- **R8, R10, R11, R12 unchanged**, and R12 is the author's.
- **Zero ticks for a THIRD consecutive critic lap, and this time the rule points at the instrument.** The
  routine says zero across two laps is a finding about direction. Direction was right again — the window
  cleared critic #25's one item and reset a clock. What the count exposes is that the loop's central honesty
  claim, 「re-run rather than read」, defends against a *stale* reading and not against a *systematically
  wrong instrument*, and it took five laps and one deeper fetch to notice. That is **WFG-119**, whose
  predicted failure turns out to have already happened five times, and it is the root objection of critic
  #26's report.

**Tick count, critic #25, 2026-09-06T0800Z: 4 of 11 (R2, R4, R5, R6), unchanged — and for the first
time in nine laps the reason is not absence.** Checked on disk at `b70e464`, re-run rather than read from a
report.

- **R7 has an object.** `docs/auto/finals/printables/WFG_printables_20260906T0620Z.pdf` exists: **29 A4
  pages**, 395,927 bytes, built by `scripts/build_printables.py` at `3e92b69`, with a manifest recording the
  sha256 of all four sources and all three fonts. I re-hashed every one of them here against the tree: all
  four sources **OK**, the PDF's own sha256 **matches**, so the kit is current rather than already stale.
  Critic #24 left a two-branch falsifiable test on this line — 「(1) if `docs/auto/finals/` holds a PDF, R7
  moves and WFG-007 is finished, say so and stop writing about the queue」 — and **branch (1) is what
  happened.** Nine days of this line reading 「no lap has ever claimed WFG-007」 ended in one window. I am
  therefore not writing about queue position again, and the constraint critics #19 through #24 were
  arguing about (position, then the lock) is settled: it was both, and both are now paid.
- **R7 still does not tick, and the reason is new, specific and cheap.** The line enumerates five
  printables — 「evidence sheet (A4), **reconciliation sheet**, related-work and SFTD059T differentiation
  panel, booth checklist, 29 dispatch sheets sample」. The PDF contains **one** of them (the booth
  checklist) and three documents that are not on the list (demo script, this Q&A bank, the detection-floor
  card). Of the four missing: the related-work panel is WFG-026 and genuinely does not exist; the dispatch
  sheets were deliberately excluded, with a reason, because `outputs/dispatch*` already holds them as
  committed PDFs; and the **reconciliation sheet exists** — `docs/submission_reconciliation.md`, 13,702
  bytes, `done(20260903T0653Z)`, the file **R6's own tick is written on**. The build's manifest says it
  「does not exist yet」. That is **WFG-130**, minutes, and it is the difference between R7 ticking this week
  and not.
- **The finding underneath is about measurement, not about the PDF**, which is good work: the kit was
  assembled from the four documents the loop writes and never compared against the five this page asks
  for. `scripts/build_printables.py:97-101` and R7's own sentence overlap in exactly one item, and nothing
  reads them together. WFG-130's done-when offers both repairs (bind the builder to R7, or correct R7 to
  the documents the booth actually needs) because either one closes the gap and the choice is a lap's.
- **R9 is unchanged and now waits on strictly less.** `release/kcf-finals-2026/MANIFEST.json` lists 17
  files and the printables PDF is not among them; R9's sentence names 「printables」 explicitly. Once
  WFG-130 settles which PDF is the real one, `make finals-bundle UPDATE=1` is the whole of R9's remaining
  agent half.
- **R1 is unchanged and its defect is now sixteen windows old and on a clock.** `web/finals.html:434`
  prints `n_entries` **326** / `n_reproducible` **268**; `docs/NUMBERS.json` holds **383** / **325**,
  counted here in one process. `registry.built_at_commit` is `41498ef`, and `git merge-base --is-ancestor
  41498ef HEAD` still **rejects** on a deepened 250-commit clone. Measured for WFG-119's prediction: the
  screen's own stamp `5f9a3b8` is **29** commits behind `HEAD` today (23 at critic #24), the branch took
  **51** commits in my 24 h, and the sandbox clones at depth **50** — so the stamp crosses the shallow
  boundary in roughly **ten hours**, after which `gates.py --mode full` goes RED in every sandbox on a
  screen that is not wrong, and CHARTER §9 spends the first lap that hits it on parking. This is my one
  `fix-before-next-row` item; see `docs/auto/CRITIC_LATEST.md`.
- **R3, R8, R10, R11, R12 unchanged**, and R12 is the author's. `gates.py --mode full` is **ALL GREEN** at
  `b70e464` in this sandbox (`1562 passed, 62 skipped`, cold, 298.9 s, against critic #24's `1545 / 62`:
  **+17 passed**, skips unchanged). Read through the GitHub MCP rather than `curl` (WFG-119 records the
  403): the twenty most recent `auto-gates` runs on `auto/dev`, run numbers 140 to 163, spanning
  2026-09-05T20:21Z to 2026-09-06T07:25Z, are **nineteen `success` and one `cancelled`** — `9ebf5a5`,
  critic #24's own push, superseded four minutes later by `3656bea`, which is green. **No red run sits
  behind a green report, so there is no gate finding and no CHARTER §4b finding this lap.** R3 still waits
  on one `make all-checks` run on the author's own laptop.
- **Zero ticks for a second consecutive critic lap, and I am recording what that rule means today rather
  than firing it.** The routine says zero across two laps is a finding about direction. The window it
  covers built the object the line has been waiting nine days for; direction was correct. What the count
  actually exposes is that **a row can be `done` and leave its readiness line ☐ forever**, because
  WFG-007's done-when (「rehearsal aids + booth checklist」) and R7's condition (five named printables)
  do not describe the same object. That is the direction finding, it is one row wide, and it is WFG-130.

**Tick count, critic #23, 2026-09-06T0200Z: 4 of 11 (R2, R4, R5, R6). No line moved, and no line has moved
for EIGHT consecutive critic laps (#16 to #23).** Checked on disk at `de7bd0a`, re-run rather than read:

- **R7 is empty on its eighth day** and it is still the whole of what this count is waiting for.
  `docs/auto/finals/` holds `BOOTH_SETUP.md`, `DETECTION_FLOOR_CARD.md` and one screenshot folder;
  `find docs/auto -name '*.pdf'` returns nothing. WFG-007 has never been claimed in twenty-three critic
  windows.
- **Critic #22 left a falsifiable test on this line and it did NOT run cleanly, so I am not reporting its
  verdict.** The test was: 「if the next lap ships a PDF, the stall was the queue's tail; if it ships another
  Q&A or gate row, no lap will voluntarily take a row whose output is a file rather than an argument.」 The
  window's lap shipped neither. It took **WFG-121**, which `docs/auto/DIRECTION.md` named **first** and which
  is the author's own row — the correct choice under CHARTER §14, and not a lap declining a file in favour of
  an argument. **A test of what a lap volunteers for cannot be run in a window where the lap was told what to
  take.** It runs cleanly for the first time in the next window, because WFG-007 is now first on the page
  **and** first in the table (this lap's one row move), so nothing else stands in front of it.
- **R3's sandbox half is green at `de7bd0a`:** `gates.py --mode full` exits 0 here (`1545 passed, 62 skipped`,
  302.5 s, COLD, against critic #22's cold `1535 / 62` at `f118bfe`: **+10 passed, skips unchanged**, like for
  like). `verify`, `snapshot-verify` and `env-check` PASS. `make baseline-verify` re-run rather than quoted:
  the same **2** differences, both the git-ignored `data/raw/firms_data/` manifests that exist only on the
  author's machine, so the author's NH-029 re-freeze still holds and CHARTER §3d makes this information.
  The CI half is green too: the five `auto-gates` runs in this window are all `success`, the newest at this head.
- **R9 re-earned rather than inherited:** `make finals-bundle` in this fresh sandbox exits 0 with
  `OK — release/kcf-finals-2026/ rebuilt byte-identically, 17 files`. It still waits on R7's printables.
- **R1 unchanged and still defective on the judged screen**, re-tested here on the deepened clone (WFG-119):
  `web/finals.html` prints `built at commit 41498ef` and `git merge-base --is-ancestor 41498ef HEAD` exits 1.
  The same screen still prints `n_entries":326` where `docs/NUMBERS.json` now holds **383** entries, counted
  here. WFG-115, WFG-113 and WFG-117 all close with one screen rebuild, and none has been done for fourteen
  windows.

**Tick count, critic #22, 2026-09-05T2330Z: 4 of 11 (R2, R4, R5, R6). No line moved, and no line has moved
for SEVEN consecutive critic laps (#16 to #22) — and this is the first of those windows where the loop did
the right thing and the count still did not move.** Checked on disk at `f118bfe`, not read from the laps
that claimed it:

- **Why no line moved, and why that is not a criticism of the window.** The window's work is WFG-114, the
  author's own NH-027 row: the fair opponent for the headline. It ticks no readiness line by design — no
  readiness line is about the science — and it was the right row. Critic #18 blamed the queue, #19 the
  queue, #20 this page, #21 lap completion. This window rules out all four: the page named the row, the lap
  took it, it finished, it was good, and readiness is unchanged. **The remaining explanation is that R7 is
  held by an artifact type no lap volunteers for.** WFG-007 is P0, `todo`, has never been claimed by any
  lap in twenty-two critic windows, and its output is a *file* rather than an argument.
- **R3's sandbox half is green; `gates.py --mode full` exits 0 here at `f118bfe`** (`1535 passed, 62
  skipped` in 306.7 s, **COLD**, against critic #21's cold `1515 / 62` at `492364c`: **+20 passed, skips
  unchanged**, like for like). `verify`, `snapshot-verify` and `env-check` PASS. `make baseline-verify`
  re-run here rather than quoted: the same **2** differences, both the git-ignored `data/raw/firms_data/`
  manifests that exist only on the author's machine, so the author's NH-029 re-freeze still holds. R3 still
  waits on one `make all-checks` run on the author's own laptop (NH-029) and on R12/NH-014.
- **R3's CI half is clean, and it was read through the GitHub MCP because this routine's `curl` still
  returns 403 (WFG-119).** `auto-gates` runs **128 to 145** on `auto/dev` carry **no `failure`**; run 145 at
  `f118bfe` (this head) is `success`; 141 and 137 were `cancelled` by a superseding push. **No red run
  stands behind a green report in this window.** All **70** consecutive push pairs in the 24-hour window
  pass `--assert-reported` (run here, one pair at a time), and every dev, paper and critic report in the
  window carries `Reviewed by:` — the two without it are `manual`, the author's own laptop.
- ⚠ **A fourth branch exists and it is green: `auto/red/20260905T2248Z`.** The 2132Z lap built WFG-114
  concurrently, could not rebase, and parked rather than forced — correct under CHARTER §4. Its gates are
  ALL GREEN at `6938e90`. It is not a readiness defect; it is recorded on this line because the readiness
  of the *product* now depends on an author decision (**NH-032**) about which of two green measurements the
  project means, and because its escalation entries were invisible to `auto/dev` until this lap imported
  them.
- **R5 keeps its tick and takes its second defect in two laps, and the second one is the first critic's
  fix going stale.** Critic #21 put a ⚠ note on `JUDGE_QA.md` Q30 giving the student 326 / 268 / 58 and
  telling them to point at the screen's 검증 레지스트리 card. One dev lap later: WFG-114 registered **57**
  `pp_uiseong_*` keys, `docs/NUMBERS.json` at this head holds **383** entries / **325** reproducible / **58**
  not (counted here with `json.load`), and `web/finals.html` still prints **326 · 268** because the screen
  has not been rebuilt. **Three counts now answer one T0 question, and the newest wrong one was written by
  the lap fixing the problem.** The note is rewritten this lap to quote no count and point at no screen;
  WFG-117 is re-scoped and is this lap's one `fix-before-next-row` item; the screen half is WFG-113, which
  now has a live instance rather than only a mutation. The tick survives because the bank's own self-count
  (41 questions, 15 / 19 / 7) is still correct, re-counted here, and `tests/test_judge_qa_bank.py` is green
  (19 passed) after this lap's edits.
- ⚠ **A second defect recorded on R5, and it is the one a judge would actually hear.** `JUDGE_QA.md` has no
  card for 「그냥 지금 불난 데만 피하면 되지 않습니까?」 — WFG-104, open since critic #17 — and as of
  `c8a3eee` the answer 「그 실험은 안 해봤습니다」 became false. The row is now `blocked(NH-032)` on its
  margin half, because the two green measurements differ by a factor of three. A ⚠ 근거 확정 전 note is on
  the Q19 answer that carries the 91, with the sentence to say meanwhile and the three numbers not to say.
- **R7 and half of R9, SEVENTH day.** `docs/auto/finals/` holds `BOOTH_SETUP.md`, `DETECTION_FLOOR_CARD.md`
  and one screenshot folder; `find . -iname '*.pdf'` outside `outputs/` and the venv returns nothing. R9's
  mechanism re-run here rather than quoted: `make finals-bundle` exits 0 with `OK — release/kcf-finals-2026/
  rebuilt byte-identically, 17 files`. WFG-007 is now **#1** on `docs/auto/DIRECTION.md`, by arithmetic
  rather than by a move: the row above it finished.
- **R8 is where the fair-opponent result will eventually be felt and is unchanged today.** No judge-facing
  surface carries the experiment: `JUDGE_QA.md`, `DEMO_SCRIPT_5MIN.md`, `web/finals.html`,
  `scripts/finals.template.html`, `docs/finals_screen_v2.md`, `BOOTH_SETUP.md` and `README.md` all return
  zero hits for the arm (grepped here). `paper/manuscript.md:386` is worse than zero: it still carries
  `[GAP: the arm that separates them, a present-perimeter baseline …]`, i.e. the manuscript tells a reviewer
  the experiment has not been run. Filed as **WFG-126** for the paper routine.
- ⚠ **The window grew an author push at 23:12Z, after this lap's measurements were taken.** `4d705df`
  closes NH-029, NH-030 and NH-031, adds CHARTER §5b (stale claims self-release after three hours) and
  §3d (the baseline freeze guards overwrites, not growth), and files two rows of the author's own —
  **WFG-121** (put the fair-opponent line beside the 91 on every judge-facing surface) and **WFG-122**
  (the budgeted bucket key). Every measurement on this line was taken at `f118bfe` and none of them is
  changed by that commit, which touches no artifact and no test. **What it does change is R8's near
  future:** WFG-121 is the first row in twenty-two windows whose entire output is judge-facing prose, and
  it is now the top row. ⚠ It is also the row that must not print a margin until **NH-032** is answered,
  and the author's decision was made from a ledger that did not yet carry NH-032 or NH-034 — this lap
  imported them from the parked branch. The critic's ids WFG-121/122/123 were renumbered to 124/125/126;
  the author's win.
- **Census for the window** (`492364c..f118bfe`, images and the `.docx` excluded): the window's authored
  work is one experiment — the arm script, its registrar, its 20 tests, `docs/present_perimeter_arm.md`
  and the paper lap's page-ceiling work. **Judge-facing share: 0 %**, and for once that is the correct
  answer rather than a slippage note: the row was science, the author asked for it, and its own escalation
  forbids putting its number in front of a judge until the author chooses. WFG-084's series takes this as
  its sixth data point **with that caveat attached**, because a census that scores this window low would be
  scoring the loop for obeying CHARTER §6.

*(Critic #21's count block, which stood here until 2026-09-05T2330Z, is preserved verbatim below.)*

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
| R1 | `web/finals.html` opens from `file://` with Wi-Fi off, all four acts advance, every on-screen number maps to a `docs/NUMBERS.json` key (mapping table committed) |  **2026-09-05T1700Z (critic #20), a second defect on this line and NOT a tick:** beyond WFG-110's six unmapped keys, the 검증 레지스트리 evidence card prints 「built at commit 41498ef」 (`web/finals.html:1924`) and `git merge-base --is-ancestor 41498ef HEAD` **exits non-zero** — the object is reachable only from `origin/auto/lap-b1989d5-superseded` and `origin/ordering-boundary`. `tests/test_finals_screen.py` gates the other stamp (`_payload()["git"]`, `:544`/`:550`/`:649`) and never reads this field. WFG-115. **2026-09-06T0457Z (critic #24), re-measured at `91d3e05` on a clone deepened to 250 commits so the shallow boundary is not the confounder:** `41498ef` is still **not** an ancestor of `HEAD`, and the same card now also prints `n_entries` **326** / `n_reproducible` **268** where `docs/NUMBERS.json` holds **383** / **325** — 57 entries apart, live, since WFG-114 registered the `pp_uiseong_*` keys at `c8a3eee`. Two of those three go away with `make finals` (`build_finals.py:629-630` re-derives both counts from the registry) and the third does not, because `built_at_commit` comes from the registry's own `built_at_git_commit`. WFG-113 carries the repair, WFG-115 the stamp.  **2026-09-06T1100Z (critic #26), and this cell is corrected rather than extended.** ⚠⚠ **The `41498ef` half of this line is WITHDRAWN: it IS an ancestor of `HEAD`.** On a clone deepened to **300** commits, `git merge-base --is-ancestor 41498ef HEAD` exits **0**, `git rev-list HEAD | grep -c 41498efbf0679276c140b3cbfc0819e5265e7733` answers **1**, `git rev-list --count 41498ef..HEAD` answers **277**, and `git branch -a --contains` names `auto/dev`, `origin/auto/dev` and `origin/Main`. Every earlier test on this line was taken inside a shorter graph than 277 commits (depth 50, then 170, then 250), so the answer they recorded was the instrument's, not the repository's. The sentences above claiming non-reachability are kept as a dated record (CHARTER §3.7) and are false. **`JUDGE_QA.md` Q35 is correct as written.** WFG-115 drops to P1 and is re-scoped to what survives: the line is stale by construction and mislabelled — the registry held **153** entries at that commit and the card beside it prints **383**. The counts half of this line is **fixed**: `web/finals.html` prints 383 / 325 against the registry's 383 / 325, counted here in one process, so WFG-113 is closed on the screen. **R1 now waits on WFG-110's six unmapped keys alone**, which I did not re-measure this lap and therefore do not tick on. | ☐ |
| R2 | The finals screen shows the evidence cards that exist today: operating point (WFG-019), reconciliation (WFG-018), detection floor (WFG-021), horizon grounding, refuge placement; rebuilt with `--verify` | **Detection-floor card written, screen not yet rebuilt (2026-09-03T2217Z dev lap).** WFG-047 released the stranded row and WFG-021 (a) shipped: `docs/auto/finals/DETECTION_FLOOR_CARD.md` states Session 19 with a registry key on every figure, `tests/test_detection_floor_card.py` (17) fails if any digit drifts from `docs/NUMBERS.json` or is attributed to the wrong fire, and `JUDGE_QA.md` Q10a/Q10b answer the 영덕-exclusion and false-alarm questions from it. Part (b) landed at `f5f8498`. **Still ☐:** nothing in `web/` has changed — putting this card and the other four onto the screen is WFG-017, and only that rebuild ticks R2  **Critic #6, 2026-09-04: the one finished card is now itself a finding.** `docs/auto/finals/DETECTION_FLOOR_CARD.md` opens 「위성은 사람보다 느렸습니다」 and this project's own `paper/manuscript.md` §4.7 says the measurement cannot say that; the manifest the delays are measured from calls the reference field the ignition. **F27 cleared 2026-09-04T0419Z (WFG-053).** The card's front sentence is now the size floor, the reference clock is named as the 기록된 발생일시 with the manifest's `provenance only` sentence quoted beside it, and the interim 99 % 목격신고 statistic was removed from the card after this lap's reviewer showed it is an unregistered year-to-date tally (CHARTER §3.3, §3.5b). **The card's text is correct today, verified line by line.** ⚠ But the gate written with it is a string tripwire, and the same reviewer escaped it repeatedly with reworded sentences (see that test's docstring for the verified-uncaught list). So WFG-017 may proceed on the card **as it now reads**, and whoever rebuilt the screen had to read the panel text rather than trust a green suite. **R2 TICKED by critic #8 at `12bf2d9`, 2026-09-04T0750Z.** All five cards are on the screen and critic #8 opened the committed screenshots to check: `5_card_operating.png` (운영점, pooled 0.138 with the three folds that have no true positive and their positive-cell counts), `6_card_detection.png` (탐지 바닥, 0.08~0.69 ha as a range with the flame-temperature caveat), `7_card_horizon.png` (240분 지평), `8_card_refuge.png` (대피 지점 배치, 20 → 24, and the claim narrowed to the one node actually re-verified), `9_card_reconciliation.png` (제출본과 정본, printing no retired value). `build_finals.py --verify` ran the three gates and the RELIABILITY tab prints their exit codes. `docs/finals_screen_v2.md` (219 lines) says for every card what it does NOT say, and the 탐지 바닥 card ships WFG-063's fix **before** the fix reached the three documents that still carry the old claim. ⚠ One defect on the ticked line, filed as WFG-067 and not enough to withhold the tick: the SYSTEM INTEGRITY panel prints `commit a562045`, which no longer exists after the lap's rebase. The durable claim gate is still WFG-062. **Critic #9, 2026-09-04: the tick holds and the defect is unchanged.** Nothing in this window touched `web/`; `git cat-file -t a562045` still answers `fatal: Not a valid object name` and `web/finals.html` still carries `"git":"a562045"`, so WFG-067 is open for a second window on a ☑ line. One thing did improve on the screen's behalf without the screen moving: the 탐지 바닥 card's sentence, which the screen shipped first and alone, is now the sentence in all four markdown surfaces too, and `tests/test_detection_ordering_is_not_claimed.py` reads the built `web/finals.html` as one of its five guarded files, so the screen is no longer the only correct document and is no longer ungated (WFG-063). ⚠ That gate's measured catch rate against a mutation set its author did not write is 2 of 20 (critic #9 F47), so the tick still rests on a lap having read the panel text, not on the suite. **Critic #10, 2026-09-04: the tick holds; WFG-067 is now in its third window on this ☑ line.** Nothing in this window touched `web/`. `git cat-file -t a562045` in this fresh clone still answers `fatal: Not a valid object name` and `web/finals.html` still carries `"git":"a562045"`. One thing worth recording against the tick rather than for it: `web/finals.html` is listed in the new `tests/test_external_figures_carry_their_scope.py` `GUARDED` tuple, and it prints two registered external figures (3,819동, 3,587명) that the gate's own two-entry `EXTERNAL_FIGURES` registry does not contain, so listing the screen there buys it nothing today (WFG-071). Coverage on this line is still a lap having looked at the panel.  **Critic #11, 2026-09-04: the tick holds; WFG-067 is now in its FOURTH window on this ☑ line.** Nothing in this window touched `web/`. `git cat-file -t a562045` in this fresh clone still answers `fatal: Not a valid object name` and `web/finals.html` still carries `"git":"a562045"`. The line of the panel whose entire job is to let a judge verify the build has now named a commit that does not exist for four consecutive critic laps, against a fix that is one rebuild plus a one-line `git cat-file -e` gate. Coverage on this line is still a lap having looked at the panel text. | ☑ |
| R3 | `make all-checks` green on a clean clone (CI) and on the booth laptop recipe in `docs/auto/finals/BOOTH_SETUP.md` | **The F13 red is repaired at `509819d`** (the lineage annotation the critic specified). `gates.py --mode full` was RED at `633c3db` — this lap's own WFG-048 row was the first document to cite `data/processed/detection/firms_first_detection.json` and `check-artifact-manifest` fired; the manifest was rebuilt at `710d5b0` and the run there is ALL GREEN (`1188 passed, 56 skipped`), which is the head recorded in this lap's report. `--assert-head` refuses a push whose gates read a different commit, and it is what a lap should read before writing a line like this one. `baseline-verify` WARN is expected off-laptop and is a soft step. **Re-verified independently by critic #5 at `5a0466e` (2026-09-04T0147Z):** `gates.py --mode full` exits 0 in a fresh cloud sandbox (`1229 passed, 62 skipped`, 163 s), now including the new `check-readme-figures` step, so `auto/dev` is green at HEAD for the second consecutive critic lap. **Re-verified independently by critic #4 at `12b8ac7`:** `gates.py --mode full` exits 0 in a fresh sandbox (`1185 passed, 62 skipped`, collected 1247), so `auto/dev` is green at HEAD for the first time in four critic laps and `--assert-head` is what makes that structural. **Re-verified independently by critic #8 at `12bf2d9` (2026-09-04T0753Z):** `gates.py --mode full` exits 0 in a fresh cloud sandbox (`1273 passed, 62 skipped` in 204 s, **COLD**, against critic #7's cold `1261 / 62` at `8e0a6ad`: +12 passed, skips unchanged). `verify`, `snapshot-verify` and `env-check` PASS; `baseline-verify` WARN, expected off-laptop, `hard: false`, eighth window and still not a finding. Green at HEAD for a fifth consecutive critic lap. **Re-verified independently by critic #9 at `ce31b91` (2026-09-04T0950Z):** `gates.py --mode full` exits 0 in a fresh cloud sandbox (`1312 passed, 62 skipped` in 206 s, **COLD**, against critic #8's cold `1273 / 62` at `12bf2d9`: **+39 passed, skips unchanged**, like for like). `verify`, `snapshot-verify` and `env-check` PASS; `baseline-verify` WARN, expected off-laptop, `hard: false`, ninth window and still not a finding. `--assert-head` and `--assert-reported` both exit 0 at HEAD. Green at HEAD for a **sixth** consecutive critic lap. **Re-verified independently by critic #10 at `3a70e16` (2026-09-04T1200Z):** `gates.py --mode full` exits 0 in a fresh cloud sandbox (`1342 passed, 62 skipped` in 152 s, **COLD** — first full run in this sandbox, so the six SRTM-gated tests skipped, WFG-039 — against critic #9's cold `1312 / 62` at `ce31b91`: **+30 passed, skips unchanged**, like for like, fourth comparable window). `verify`, `snapshot-verify` and `env-check` PASS; `baseline-verify` WARN, expected off-laptop, `hard: false`, tenth window and still not a finding. `--assert-head` and `--assert-reported` both exit 0 at HEAD. Green at HEAD for a **seventh** consecutive critic lap. **Re-verified independently by critic #11 at `83f49bc` (2026-09-04T1400Z):** `gates.py --mode full` exits 0 in a fresh cloud sandbox (`1367 passed, 62 skipped` in 196 s, **COLD** — first full run in this sandbox, so the six SRTM-gated tests skipped, WFG-039 — against critic #10's cold `1342 / 62` at `3a70e16`: **+25 passed, skips unchanged**, like for like, fifth comparable window). `verify`, `snapshot-verify` and `env-check` PASS; `baseline-verify` WARN, expected off-laptop, `hard: false`, eleventh window and still not a finding. Green at HEAD for an **eighth** consecutive critic lap. ⚠ And this is the window that shows what the sentence is worth: the suite was green, and one of its passing tests (`tests/test_juso_yeongdeok.py:11`) was asserting that 영덕's 시군구 code is 47920 over an artifact lying 45 km outside 영덕 (critic #11 F54, WFG-075/076, NH-022). Gate green means no gate disagreed, not that the tree is right. **Re-verified independently by critic #13 at `baf6962` (2026-09-04T2000Z):** `gates.py --mode full` exits 0 in a fresh cloud sandbox (`1377 passed, 62 skipped` in 178 s, **COLD** — first full run in this sandbox, so the six SRTM-gated tests skipped, WFG-039 — against critic #12's cold `1376 / 62` at `c65dc56`: **+1 passed, skips unchanged**, like for like, seventh comparable window). `verify`, `snapshot-verify` and `env-check` PASS; `baseline-verify` WARN, expected off-laptop, `hard: false`, thirteenth window and still not a finding. Green at HEAD for a **tenth** consecutive critic lap. ⚠ And this is the window that shows what the CI half of this line is worth, which the sandbox half cannot: `auto-gates` was **RED on `auto/dev` for six consecutive pushes** (runs 86–91, `201c554` through `e4a7304`) while every lap that pushed them read ALL GREEN in its own sandbox. One test, `tests/test_finals_screen.py::test_the_stamp_gate_is_graded_against_the_ways_a_stamp_goes_wrong`, built a probe commit with `git commit-tree` and inherited a committer identity the runner does not have. Fixed at `21b8740`; runs 92, 93 and 95 are `success` and run 95 is this head. The residue worth recording against this line rather than for it: the first red was 16:03Z and the fix 18:39Z, **2 h 36 min against CHARTER §4b's 「catch it within the hour」**, and the hourly ci-red routine's own run on it produced a report and no fix because a concurrent lap had landed the same repair first. **Re-verified independently by critic #14 at `ed35f0d` (2026-09-04T2300Z):** `gates.py --mode full` exits 0 in a fresh cloud sandbox (`1453 passed, 62 skipped` in 208.9 s, **COLD** — first full run in this sandbox, so the six SRTM-gated tests skipped, WFG-039 — against critic #13's cold `1377 / 62` at `baf6962`: **+76 passed, skips unchanged**, like for like, eighth comparable window and the largest single-window gain this line has recorded, all of it WFG-062's `tests/test_withdrawn_claims_registry.py`). `verify`, `snapshot-verify` and `env-check` PASS; `baseline-verify` WARN, expected off-laptop, `hard: false`, fourteenth window and still not a finding. `--assert-head` exits 0 at HEAD. Green at HEAD for an **eleventh** consecutive critic lap. The CI half also recovered: `auto-gates` runs 92, 93, 95, 96, 97, 98 and **99 (this head) are `success`** (94 cancelled by a superseding push), so the six-red episode of runs 86–91 is closed for a second consecutive window and no red run sits behind a green report here. **Re-verified independently by critic #15 at `43710f7` (2026-09-05T0206Z):** `gates.py --mode full` exits 0 in a fresh cloud sandbox (`1464 passed, 62 skipped` in 317.3 s, **COLD** — first full run here, so the six SRTM-gated tests skip, WFG-039 — against critic #14's cold `1453 / 62` at `ed35f0d`: **+11 passed, skips unchanged**, like for like, ninth comparable window). `verify`, `snapshot-verify` and `env-check` PASS; `baseline-verify` WARN, expected off-laptop, `hard: false`, fifteenth window and still not a finding. `--assert-head` and `--assert-reported` both exit 0 at HEAD. Green at HEAD for a **twelfth** consecutive critic lap. ⚠ The CI half went red twice inside this window and the reason is new: `auto-gates` runs **103 (`a2a2994`) and 104 (`c8124a8`) are `failure`**, and in both the **`gates` job passed and the new `promote` job failed** — the fast-forward of `Main` that CHARTER §4c introduced at `a2a2994` cannot run while `Main` is a protected branch requiring a pull-request review, which is an author action nobody had filed (now **NH-025**). Fixed at `b3244f8` by making a refused fast-forward a warning rather than a red run, 20 minutes after the first red, well inside CHARTER §4b's hour. Runs 105, 106 and **107 (this head) are `success`**. Recorded here because it changes what a red `auto-gates` run means on this line: from 09-05 a red run can be a promotion refusal with green gates behind it, and a lap must read the **job**, not the run. **2026-09-05T1217Z (WFG-037), a note and NOT a tick — the dev lap does not tick, the critic does (CHARTER §10).** `docs/auto/finals/BOOTH_SETUP.md` now exists, so the sentence above it is history. ⚠ And writing it falsified this line's own command: **`make all-checks` does not pass, and not only off-laptop.** It aborts at `baseline-verify` with six differences against the freeze at `89730db89921`, of which only two are the missing `data/raw/firms_data/` manifests; the other four — the registry entry count and three tracked `pace_*.json` artifacts — are in every clone and will abort the same command on the author's laptop. `gates.py` treats the step as soft (`hard: false`), which is why eighteen windows of 「WARN, expected off-laptop」 read past it. The re-freeze needs the raw bundle and is the author's (**NH-029**); the recipe's §1.1 sends the booth morning to `gates.py --mode full` instead. **So the CI half of this line is unchanged and green; the booth half now has a written recipe whose every command was executed and whose own readiness command is the one that fails.** The rehearsal half is R12 / NH-014 | ☐ |
| R4 | A 5-minute demo script in Korean with per-act timings and the sentence for each judge type's interruption (`docs/auto/DEMO_SCRIPT_5MIN.md`) | **The file exists as of the 20260905T0025Z dev lap (WFG-003).** Korean, DRAFT-labelled per CHARTER §9, six timed segments summing to exactly 300 s over `docs/FINALS_DEMO.md`'s four acts plus an opening and a limits close, one interruption sentence for each of the five judge lenses, and a §3 mapping table of 35 rows (23 화면 / 12 구두) each carrying a registry key or a named artifact, where 화면 means a card in scripts/finals.template.html actually renders it (not merely that the key sits in the built page). `tests/test_demo_script_5min.py` (9) reads that table mechanically and was graded 6 of 6 against mutations written to break it. **The dev lap does not tick this line — the critic does (CHARTER §10)**, and the half a test cannot reach is whether five minutes of Korean fits in five minutes: the segment times are design values, not a rehearsal, and §5 of the document says so. R12/NH-014 is where a human reads it aloud. **R4 TICKED by critic #15 at `43710f7`, 2026-09-05T0200Z**, on the independent check recorded in the header above: 300 s exactly, five lenses, 33 registry keys resolved and value-matched by hand, two quoted screen sentences found in the built page. The half a test cannot reach is unchanged and the tick does not claim it — five minutes of spoken Korean fitting in five minutes is R12/NH-014, and §5 of the document says so in the document. ⚠ Defect carried on the ticked line: WFG-095, the **[버림]** markers on caveat-only sentences in 2막 and 3막 — **closed at `9345848`**. **2026-09-05T0625Z (WFG-100), correcting this cell rather than the tick (CHARTER §10 — the dev lap does not tick):** the sentence above saying 「the segment times are design values」 is no longer true. They are now a *measurement* — 1,684 spoken syllables allocated over 300 s at one rate of 5.61 syl/s, giving 29 / 44 / 50 / 60 / 59 / 58 s where the design values were 25 / 45 / 55 / 75 / 55 / 45 and implied six different rates spanning 1.62× (`docs/demo_script_pace.md`, `data/processed/demo_script_pace/pace_20260905T0625Z.json`, `tests/test_demo_script_pace.py`). **The half a test cannot reach is unchanged and this note does not claim it:** whether that rate is sayable is still R12 / NH-014, a human with a stopwatch. The critic owns whether the tick survives the re-budget. | ☑ |
| R5 | Judge Q&A bank v2 complete: every T0 answer cites a file; no purged phrasing remains (`tests/test_judge_qa_bank.py` green) | Invariants met: `docs/auto/JUDGE_QA.md` 33 questions, tiers 14/13/6, 18 tests green in `gates.py --mode full` at `1113388`, WFG-002 `done(20260903T1536Z)`. **Tickable at `1c1561e` (2026-09-03T2017Z dev lap):** the §0 bullet that told the student the repository was wrong about "6 → 34" (the 폐기된 452계열 bracket; canonical is 6 → 66) is rewritten onto `docs/ssot_audit_2026-09-03.md` §1 and now tells the student explicitly NOT to say 오타 at the booth. CRITIC F1 `done(1c1561e)`. `tests/test_judge_qa_bank.py` 18 passed, `check_forbidden` and `tests/test_rescue_lineage_ssot.py` green on the rewritten text | ☑ |
| R6 | 제출본 대비 정본 reconciliation sheet exists, in Korean, one page, and JUDGE_QA links to it | `docs/submission_reconciliation.md` (Korean, 11 rows, spoken lines); `JUDGE_QA.md:34` links to it; WFG-018 `done(20260903T0653Z)`; row 8 corrected by WFG-004 at `6a2c8a3` | ☑ |
| R7 | Printables as PDF under `docs/auto/finals/`: evidence sheet (A4), reconciliation sheet, related-work and SFTD059T differentiation panel, booth checklist, 29 dispatch sheets sample |  **2026-09-05T1700Z (critic #20):** still nothing. `docs/auto/finals/` holds two `.md` files and one screenshot folder and no PDF, on the sixth day this line has been held by a row no lap has claimed. Critic #19's falsifiable test resolved (WFG-109 closed, printables absent), so **WFG-007 is raised P1 -> P0** and is second on `docs/auto/DIRECTION.md`. The printing and the poster stay the student's; the files and the build script are the agent's and are what P0 buys. **2026-09-06T0457Z (critic #24): day nine, and for the first time the row is claimed.** `find docs/auto -name '*.pdf'` still returns nothing at `91d3e05`, but `7233743` set WFG-007 `in-progress(20260906T0320Z)` three minutes after the 03:17Z lap woke, with the row first in the table and first on `DIRECTION.md` — which is critic #23's falsifiable test actually running. The claim was still in flight when this lap ran its gates, so the verdict belongs to critic #25, not to me. ⚠ If that lap died, **NH-035** is why the row is not releasable at 06:17Z. | ☐ |
| R8 | `README.md` has a Round-4 section and the English abstract draft; forbidden-string and collision gates green | **Sourcing half now durable, 2026-09-04 (critic #5).** Every figure the opening paragraph prints was re-opened at its primary page this lap and every one holds (경상북도 보도자료: 99,289 ha / 149시간 / 3,819동 / 2,246세대 3,587명 / 1조 505억, and the 「1986년 이래 역대 최대 피해 면적」 superlative carried by that release itself; 산림청 2025-05-16 for 347건 / 104,788 ha over 봄철 산불조심기간 1.24~5.15). `data/processed/external/fire_2025_scale.json` + 16 `fire2025_*` registry keys + `check-readme-figures` + 44 new tests mean the figures can no longer be rewritten silently. **(b) is CLOSED at `e5aaaa7`/`28b4c38`, verified by critic #6 at `b855943`:** the 「약 43 %」 / 「about 43 %」 sentence is gone from both languages, `README.md` prints no share at all, and the tripwire now scans both whole paragraphs instead of the one line that carried `104,788`. **Still not tickable on (a) alone:** no Round-4 section and no abstract draft yet (WFG-010). Previously: **Still not tickable, for two reasons:** (a) no Round-4 section and no abstract draft yet (WFG-010), and (b) the scope note's 「about 43 %」 sentence at `README.md:210-211` / `:528` is false and contradicts this repository's own `fire2025_chain_share_of_nationwide_pct = 94.8` (critic #5 F21). Previously: **Half recovered, 2026-09-04.** The falsifiable-in-one-search half is fixed by two laps: the 0037Z manual lap rewrote both opening paragraphs onto 99,289 ha, and the 0017Z dev lap sourced every figure to a URL it opened, corrected the nationwide comparison's **period** (봄철 산불조심기간 2025-01-24~05-15, not March) against the 산림청 release, withdrew the 95 % share claim as basis-mixing, and added `tests/test_motivating_event_figures.py` — the gate these figures never had. **Still not tickable:** no Round-4 section and no abstract draft yet (WFG-010), which is the other half of this line. Original finding: **Moved backwards this window.** No Round-4 section and no abstract draft yet, and `12b8ac7` rewrote the existing opening paragraph in both languages to figures that are wrong: 45,157 ha for a chain that burned 99,289 ha, and 영덕 8명 against this repository's own correction to 10 (critic #4 F16/F17, WFG-043). The gates are green because none of these figures has a registry key, which is the point of WFG-049. This line cannot be ticked while the paragraph above the Round-4 section is falsifiable in one search | ☐ |
| R9 | The release bundle `release/kcf-finals-2026/` (WFG-036) exists: `web/` whole, printables, `README_KO.md` with the 10-line run recipe, `CITATION.cff`, and `make finals-bundle` rebuilds it byte-identically | **v1 landed 2026-09-05 (WFG-036, dev lap 20260905T0355Z), and the dev lap does not tick this line — the critic does (CHARTER §10).** `release/kcf-finals-2026/` holds the four screens (`finals`, `console`, `field_view`, `refuge_placement`), the fonts and poster, `LICENSE`, `CITATION.cff`, a ten-step Korean `README_KO.md` and `MANIFEST.json`. `make finals-bundle` re-assembles the folder, re-derives every SHA-256 and exits non-zero naming any file the committed manifest does not describe; `tests/test_finals_bundle.py` (7) hashes the sources independently of the builder. ⚠ **Two things this v1 does not have, and they are why it is not tickable yet:** the printables the line names (R7 / WFG-007 — none exist), and the booth recipe the run steps stand in for (WFG-037). ⚠ The payload (`web/`, `CITATION.cff`, `LICENSE` inside the bundle) is **generated and git-ignored**, so a clean clone holds only `README_KO.md` and `MANIFEST.json` until the command is run once; the reasoning is in `docs/finals_bundle.md` and a critic who reads R9 as requiring a committed payload should say so rather than inherit the choice. **Answered by critic #16, 2026-09-05: R9 does NOT require a committed payload.** The line's own condition is that `make finals-bundle` rebuilds it byte-identically, which presupposes a build; I ran it in a fresh cloud sandbox and it exits 0 with `OK — release/kcf-finals-2026/ rebuilt byte-identically, 16 files`. The choice is accepted and is not what holds the line. **Still ☐ for exactly two things the line also names:** the printables (R7 / WFG-007) and the booth recipe (WFG-037), which is why WFG-037 was moved directly under WFG-036 in the table this lap. **2026-09-05T1217Z (WFG-037), a note and NOT a tick:** the booth recipe half is now written, and the bundle gained a seventeenth file — `check_bundle_copy.py`, which verifies a COPY of the folder against the manifest that travels with it, reads and never writes, and imports nothing outside the standard library so a borrowed machine with no repository can run it. It exists because this line's mechanism was found to answer a different question than the booth asks: `make finals-bundle` overwrites the bundle from the tree before hashing, so a file corrupted **on the stick** is repaired rather than reported (measured by appending seven bytes to the bundle's `finals.html`: the run printed `OK`), and the builder never enumerates the folder, so a file an earlier run left behind ships on the stick while the run reports byte-identity (**WFG-108**). The line still waits on the printables (R7 / WFG-007) | ☐ |
| R10 | ~~AI ledger~~ **Withdrawn 2026-09-04.** The organisers confirmed to the author that no AI-disclosure artifact is required (NH-008), and `AI_DISCLOSURE.md` was removed at the author's instruction. `ROUTINE_PROMPTS.md` and the `Co-Authored-By` trailers remain under CHARTER §9 as booth-explainability practice, not as a compliance artifact | Withdrawn, not failed | — |
| R11 | `docs/HANDOFF_ROUND3.md` §5.1 and every date in `docs/auto/` say `auto/dev`, 10-16 and 10-24 | The three live lines CRITIC F7 named are fixed at `1c1561e`: `CHARTER.md:11` and `RUBRIC.md:20` now read 10-24, and NH-006's question text is annotated as a superseded record rather than edited (§3.7). The `research/sweeps_2026-09-03/*` files and the two BACKLOG rows that quote the 10.18-vs-10.24 question predate or describe the NH-006 decision and keep their text as dated records. **Still ☐ for the branch half only:** `docs/HANDOFF_ROUND3.md:898` states "All work stays on `round3-dev`", which is WFG-024 and blocked on WFG-023 | ☐ |
| R12 | The author has run the booth recipe on the actual laptop once and closed NH-014 | | ☐ (author) |
