# CRITIC_LATEST — critic #45, 2026-09-08T2000Z

*The next dev lap reads this file before it claims a row (CHARTER §4 step 3). Reviewed head:
`9c24a8b`. ⚠ **This clone is shallow and SHALLOWER than critic #44's:**
`git rev-parse --is-shallow-repository` = **true**, `git rev-list --count HEAD` = **50**, and the
oldest resolvable commit is `088203c` at **00:22Z on 09-08**, so this clone reads about **19.6
hours**, not 24. I claim nothing about anything before 00:22Z and **no ancestry or reachability
claim at all** (DIRECTION's standing rule). ⚠ One consequence, recorded so the next lap does not
repeat it: `git show 088203c` presents the entire tree as additions because its parent is outside
the clone, so a naive 「what changed in 24 h」 read of that commit reports 2,669 files including
`outputs/dispatch/**` and a `data/raw/**` CSV. **Nothing was added or modified there.** Full
report: `docs/auto/reports/2026-09-08T2023Z-critic.md` — the readings below were taken from 20:00Z and
the report stamp is when `report.py` ran.*

## The one thing to read first: **there is no red gate anywhere today, and that is the first time this week a critic lap can write that sentence.**

- `gates.py --mode full` exits **0** at `9c24a8b`: `1763 passed, 63 skipped, 2 xfailed`, pytest
  **322.5 s**; `verify`, `snapshot-verify`, `env-check` PASS; the `baseline-verify` WARN is the
  documented CHARTER §3d sandbox state. Read unpiped.
- `--assert-head` exits 0. `--assert-reported --base 088203c` exits 0 over **56** substantive paths.
- **GitHub agrees.** Through the GitHub MCP (`curl` against `api.github.com` is still refused here,
  WFG-119): `auto-gates` runs **240 to 257** on `auto/dev` are **16 `success`, 2 `failure`**, and
  **both failures are closed**. Run **257** at this exact head is `success`.
- **`Main` is following again.** `git ls-remote origin Main` answers **`9c24a8b`** — the same commit
  as `auto/dev`. Critic #44 found it stranded at `6ecc386`; WFG-193's guard (`b2cda36`) and run 254
  cleared it.

⚠ **The second failure in the window was NOT the artifact upload and it is worth reading.** Run
**255** (`b7c1837`) went red on `tests/test_finals_acts.py::test_the_four_acts_advance_in_a_real_browser`
with `CDPError: no page target on port 51449 within 30.0s (last: Connection refused)`. The 1758Z lap
converted that one error into a `pytest.skip` and re-raises every other `CDPError`. **I checked the
discrimination rather than reading the commit message, and it holds:** `page_target()` is called at
exactly one site (`scripts/check_finals_acts.py:313`), against `about:blank`, **before**
`Page.navigate` reaches `web/finals.html`, so 「no page target on port」 is unreachable from anything
the screen does; a JS throw raises `CDPError("JS threw: …")` from `evaluate()` and still fails. The
residual risk — a Chromium that stops starting permanently now skips in silence while `finals-acts`
carries `if-no-files-found: warn` — is filed as **WFG-196** by the lap itself rather than hidden.
That is the right shape and I am not filing against it.

---

## `fix-before-next-row` — ONE item: **WFG-199. One command, and it is the judged screen.**

**Run `make finals` before you claim a row**, and re-point `release/kcf-finals-2026/MANIFEST.json`
in the same commit (WFG-152).

Measured here at `9c24a8b`, unpiped: `web/finals.html`'s embedded payload carries `"git":"25f6b60"`
and `git rev-list --count 25f6b60..HEAD` answers **22** against `tests/test_finals_screen.py:540`'s
`STAMP_MAX_COMMITS_BEHIND = 30`. **Critic #44 measured 16 at `0cca093` three hours ago.** Six
commits in three hours, about two an hour; this lap's own report commits take it to roughly 24. A
dev lap costs 3 to 5 commits, so the next lap lands near 28 and **the lap after it trips the assert
on its claim commit alone**. That is NH-045 (BLOCKER, open) replaying for the third time, and for the
third time the routine that can see it coming is the one routine forbidden to clear it.

⚠ **Stamp a commit that is reachable from `origin/auto/dev`**, not your own unpushed HEAD:
`tests/test_finals_screen.py::test_the_escape_this_gate_cannot_close_is_still_open` requires it, and
`088203c`'s report records a lap that learned this the expensive way.

**This is not a fix for the class.** The class is NH-045's A-or-B recurrence rule and NH-043, both
still the author's. Filed with headroom, exactly as critic #42 filed WFG-187.

**Then take the table: WFG-127 is position 1.** It was position 1 at critic #44 too and no dev lap
has run since (the 1817Z slot was ceded to research), so `README.md:232` still reads
「고원이 아니라 뾰족한 봉우리」 — measured again here, unchanged.

---

## The root objection

**The strongest claim this project makes is now labelled, on its own front door, as a bound its own
model does not reach — and the one experiment that would replace that bound with a number is
priority P1, while the material that experiment needs has been committed in this repository the
whole time and no lap has ever looked at it.**

The bank files the question as **`docs/auto/JUDGE_QA.md:1393`, Q36, tier T0** — the tier whose own
header says a card you cannot answer costs you that judge — and the answer it gives the student is
「맞습니다」 with nothing measured after it. `README.md:637-645` says the same in English: 42 is
「an **upper bound** — what a *noiseless* forecast would buy, not what this project's own model
buys」, and 「실제 값은 그보다 적으며, **얼마나 적은지는 이 저장소의 어떤 실행도 측정하지
않았습니다**」. `docs/present_perimeter_arm.md` §5 says it in the document's own words. WFG-125 is
the row for it, and it has sat at **P1** below twelve P0 rows.

**The cheapest test, and it is the finding.** `data/processed/spread_v2_lofo_oof_cells.csv.gz` holds
the shipped model's **leave-one-fire-out out-of-fold** per-cell probabilities: 151,904 rows,
columns `fire_id, op_from, row, col, label, dist_band, dist_to_fire_m, far_band, prob`, with
**20,749** cells for `yeongdeok_2025` and **82,736** for `uiseong_andong_2025` — the two regions the
routing arms use. Those are predictions the model made on a fire it did **not** train on. That is
exactly 「a field the model produced rather than the field it is graded on」. Shape check, measured:
`hazard_uiseong_andong_2025.npz`'s `haz_stack` is `(5, 135, 128)`, and the uiseong OOF cells span
rows 23-123 and cols 0-126 — inside that grid — with 18 `op_from` slices against 5 committed hazard
times.

⚠ **What I did NOT verify, and the dev lap must, before anything else:** that the OOF `row`/`col`
indexing shares an origin and CRS with the hazard stack the router consumes, and how 18 `op_from`
slices map onto 5 committed hazard times. If they do not align, WFG-125 falls back to its written
branch — and that record is then worth **more**, because it can name the file and say precisely why
it cannot be used, instead of saying no such field exists.

**Routing only. No retrain, no re-acquisition, no committed artifact modified** (CHARTER §3 rule 2
and §3.11 both hold).

---

## The other findings

**F2 · 창의성 has a written answer and no judge can reach it.** At `9c24a8b`, a `grep -cE` over the
alternation of 창의 and 독창 answers **2** on `docs/auto/JUDGE_QA.md`, **0** on `web/finals.html`,
**0** on `docs/auto/DEMO_SCRIPT_5MIN.md` and **0** on `release/kcf-finals-2026/README_KO.md`.
Meanwhile `docs/creativity_card.md` exists — 149 lines, 10 hits, bound by
`tests/test_creativity_card.py` — and **is not in the printed kit**:
`docs/auto/finals/printables/manifest_20260908T1529Z.json` lists six source documents
(`BOOTH_SETUP`, `DEMO_SCRIPT_5MIN`, `JUDGE_QA`, `submission_reconciliation`,
`DETECTION_FLOOR_CARD`, `RELATED_WORK_PANEL`) and this is not one of them. The row is worth **20
points on both rubric tables** and the 심사기준 names it first. Written into **WFG-194**; no new row.

**F3 · The judge drill found a rubric bullet at zero on every surface, and it is not the one anyone
has been watching.** 설계와 방법론 (20 points, both tracks) lists 「일정 및 팀원(개인의 경우 제외)
역할 배분의 타당성」; for an individual entry the 팀원 half is excluded by the criterion's own text
and the **일정** half is not. Measured at `9c24a8b`: `grep -n 일정` answers **0** in
`docs/auto/JUDGE_QA.md`, **0** in `release/kcf-finals-2026/README_KO.md`, **0** in `web/finals.html`,
and its one hit in `docs/auto/DEMO_SCRIPT_5MIN.md:70` is 「일정 크기」 — 「a certain size」, a false
positive. Forty-six cards and no 일정 card. **WFG-027** exists, is P1, and estimates **hours**.
⚠ **I did not move it**: my one reorder went to WFG-125, and raising a priority without moving the
position is the exact defect critic #42 recorded against critic #41. It is written into the row as
**the next critic lap's reorder candidate**.

**F4 · The head of the `todo` block is a P1 infra row again — and this lap can finally name the
mechanism instead of moving another row.** Critics #40, #42 and #44 each spent their one reorder on
this shape and each recorded that it recurred. The reason is not that the moves were wrong. It is
that **new rows are inserted near the TOP of the table, so a new P1 row is born ABOVE the P0
block.** Measured at `9c24a8b` before my own edits: WFG-189, WFG-191, WFG-192 at table lines 49-51
and WFG-196, WFG-197, WFG-198 — all three filed in the last 24 h, all P1 — at lines 53-55, with six
P0 `todo` rows below them. So the gate WFG-183 and WFG-191 ask for must check **order** (no non-P0
`todo` row above a P0 `todo` row), not only **shape**, or it will pass a table that still points a
fresh lap at work §14b forbids it to take. Written into WFG-191. **No fourth row filed**, for the
same reason critic #44 declined one.

---

## The baseline, re-derived rather than read

✅ **ALL GREEN on the routine's default clone, read unpiped.** `gates.py --mode full` exits **0** at
`9c24a8b`: `1763 passed, 63 skipped, 2 xfailed`, pytest **322.5 s**. `--assert-head` 0,
`--assert-reported --base 088203c` 0 over 56 paths. **The bootstrap succeeded on the FIRST attempt**
this lap, `pins_ok: true`, `stack_ok: true` — ending the two-lap `ReadTimeoutError` streak critics
#43 and #44 both recorded. Nothing in the repository was implicated then and nothing is now.

✅ **GitHub's own runs (CHARTER §4b): NO open finding.** Runs 240-257 on `auto/dev`: 16 `success`,
2 `failure` (**253**, the `upload-artifact` 403 — closed by WFG-193/`b2cda36`, and run 254 uploaded
2,238,011 B and 9,792 B an hour later, settling it as transient; **255**, the browser-launch
CDPError — closed by `298a09c`). Runs 256 and 257 are `success`. `Main` = `auto/dev` = `9c24a8b`.

✅ **Report certification.** Every **dev**, **critic** and **paper** report in the window carries
`Reviewed by:`. Two do not and neither is a finding: `2026-09-08T1132Z-manual.md`, which critics
#42, #43 and #44 each declined to file and I decline for the same reason; and
`2026-09-08T1836Z-research.md` — checked rather than assumed, the **only** other research report in
the tree (`2026-09-06T1838Z-research.md`) has none either, so this is the research routine's
standing convention and not a regression. Recorded here so a later lap need not re-derive it.

✅ **Every push in the window carried a report.** Read run by run through the MCP: run 254 carried
`2026-09-08T1718Z-critic.md` (`dc8fa9f` + `be05c1c` in one push), run 255 carried
`2026-09-08T1737Z-manual.md` with `b2cda36` (the workflow change) in the same push, run 256 carried
`2026-09-08T1758Z-manual.md`, run 257 carried `2026-09-08T1836Z-research.md`.

✅ **`factchk` on the window's one new claim about the world, verified independently.** The research
lap's 국립산림과학원 Ready-Set-Go item: I opened
<https://biz.heraldcorp.com/article/10675702> myself and it carries, verbatim,
「'준비(Ready)-실행 대기(Set)-즉시 실행(Go)'으로 이어지는 단계별 체계」 and 「화선 도달 8시간 전
산불확산 예측 정보를 바탕으로 고령자 등 안전 취약계층의 선제적 대피를 돕고, 5시간 전에는 대상
주민이 안전한 곳으로 지체 없이 이동하도록 유도할 방침」, dated **2026-02-12**. Source, date,
wording and both figures are exactly as recorded. **And the figures stayed where CHARTER §13 puts
them:** 8시간 / 5시간 / Ready-Set-Go appear in **no** README, screen, script, manuscript or bundle
file. The one hit for 76 % → 88 % outside the knowledge note is `docs/auto/JUDGE_QA.md:688`, where
it is a **prohibition** — 「기관의 계획 발표를 언론이 옮긴 것」, do not compare accuracy in either
direction — which is the licensed use, not a leak.

✅ **The abstract's one world claim checks out.** `README.md:623` calls the March 2025 Gyeongbuk
fires 「the largest on Korea's record by burned area」 and gives **no hectare figure**, which is the
correct shape: public sources give 104,788 ha (2025 national), 99,289 ha (the Gyeongbuk event) and
45,157 ha (a provincial interim tally) for overlapping scopes, and that disagreement is exactly the
`12b8ac7` / NH-015 failure. A claim without a number cannot repeat it.

---

## What this lap did NOT find, said plainly

- **No red gate on either machine, no test failure, no fabricated number.** `make verify` PASS at
  this head; every figure in the window's new prose is registered, licensed by a pragma, or absent
  by design.
- **No leakage-style defect introduced this window.** Nothing in the window touched a model, a
  split, a metric, an arm, a coupling or a protocol. The standing leakage issue is the one the
  repository itself documents and it is the root objection above.
- **The backlog's malformed-row count did not grow: 10 before this lap and 10 after** — the same ten
  (WFG-167, WFG-181, WFG-182, WFG-188, WFG-175, WFG-168, WFG-133, WFG-115, WFG-112, WFG-149).
  ⚠ **I wrote two more while filing WFG-191's own finding** — an unescaped pipe inside a
  `grep -cE` alternation in WFG-194 and inside a `^| WFG-` pattern in WFG-191 — plus a WFG-199 row
  with the status cell missing. All three were caught by re-parsing the table before the commit and
  rewritten without the pipe. That is the **twelfth, thirteenth and fourteenth** instance of
  WFG-191's defect, two of them committed by the lap reading WFG-191 at the time, which is the
  argument for a gate and is written into the row rather than hidden.
- **No JUDGE_QA card is added by this lap, and none may be:** the critic routine must not edit a
  printables `SOURCES` file (DIRECTION, WFG-152). The drill's two findings are F2 and F3 and both
  are rows.
- **No new NEEDS_HUMAN entry.** Nothing this lap found is blocked on the author; twenty entries are
  already open (14 DECISION, 6 FYI or BLOCKER) and a twenty-first would be noise.
- **No author decision to apply.** Both channels checked: Gmail
  `from:siyeong0318@gmail.com subject:"WildfireGuardian autoloop" newer_than:14d` returns threads
  that each hold exactly **one** message, every one labelled `SENT` — the loop's own reports arriving
  back at the same address. `pull_request_read` on PR **#31** returns `[]`. `decisions.py apply` was
  not called and `docs/auto/decisions_seen.json` is unchanged.

## The one `Do NOT edit` note, RE-STATED and NARROWED after re-checking (CHARTER §14c, NH-036 A)

**Do not put a present-perimeter margin value — 9, 27, 5, 19 or 86 — into `README.md:220-239`.**
That is the whole of it: twenty lines, one prohibition.

**Premise re-checked, not inherited.** `docs/auto/NEEDS_HUMAN.md:1391` (NH-032) and `:1524` (NH-034)
are both still `open`, and both headers read **(by 2026-09-08)**, which is **today** — critic #44
wrote that they were 「overdue by a day」 and that is corrected here rather than repeated.

⚠ **Narrowed, and the narrowing matters.** Critic #44's list included **42** and **91**. It should
not have: `README.md:236-238` is *required* by DIRECTION to state the **42** with its two binding
caveats, and it does. A note that forbids a number the same twenty lines are obliged to carry is a
note that contradicts itself, and it is exactly the kind of over-broad freeze NH-036 option A was
written to stop. Verified at `9c24a8b`: within `:220-239` only **42** appears, twice, both times
inside its caveat block; none of 9, 27, 5, 19, 86 or 91 appears.

**It freezes no file and no question.** WFG-127 (iv) must edit `README.md:232`, and that edit is
prose about a **grid**, not about a result. **It expires at critic #46** unless that lap re-reads
NH-032 and NH-034 and re-states it.

## The one thing worth copying forward

**Two laps in this window each closed a red CI run by first ruling out the explanation that would
have been convenient.** The 1737Z lap had built a 「the Actions artifact store is full」 theory and a
NEEDS_HUMAN entry to go with it, then downgraded both to an FYI because critic #44's measurement —
a 2.24 MB upload succeeding six minutes before a 9.7 kB one failed — runs backwards for that theory.
The 1758Z lap turned a browser failure into a skip only after raising each kind of `CDPError` through
the test body in a throwaway harness to confirm the launch error skips and `JS threw` still
propagates. Neither lap argued from its commit message. That is why the third finding in this report
is a thing nobody had looked at rather than a thing somebody had got wrong.
